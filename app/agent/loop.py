import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agent.tools import TOOL_DEFINITIONS, execute_tool
from app.llm import AGENT_MODEL, client
from app.models.anime import Anime
from app.models.reception import ReceptionSignal

MAX_TOOL_ROUNDS = 3
MAX_HISTORY_TURNS = 6

SYSTEM_PROMPT = """You are the recommendation agent for AnimeSZN, an anime discovery app.

A user will ask you to find a specific anime or to recommend something to watch. Reason about
the request and use the available tools:
- search_by_title: the user named a specific anime
- semantic_search: mood/theme/description-based requests
- find_similar: "more like X" requests (resolve X with search_by_title first if needed)
- check_reception: MUST be called on every candidate before you recommend it

Rules:
- You may chain tool calls (e.g. resolve a title, then find similar titles, then filter).
- Before finalizing, call check_reception on each anime you are about to recommend. If a
  candidate is flagged widely_criticized or has a low sentiment ratio, either drop it or
  include it with an explicit caveat explaining the divisive reception -- never recommend
  it silently as if it were uncontroversial.
- You have at most {max_rounds} rounds of tool calls before you must finalize.
- Always end by calling the `respond` tool with a short message and per-title rationale
  (and a caveat field for any title with reception concerns). Never answer in plain text.

You may be continuing a multi-turn conversation -- earlier user questions and your own prior
replies (with a short recap of what you recommended) may already appear in this message list.
When the user refers back to your previous answer ("those", "the first one", "not that one",
"something lighter than what you just gave me"), resolve the reference from that history rather
than asking them to repeat it. Don't re-run search_by_title or semantic_search for a title you
already resolved earlier in the conversation -- reuse its anime_id directly, and only call tools
for what's actually new.
""".format(max_rounds=MAX_TOOL_ROUNDS)


@dataclass
class RecommendationCard:
    anime_id: int
    title: str
    rationale: str
    caveat: str | None
    score: float | None
    community_flag: str | None
    image_url: str | None


@dataclass
class AgentResult:
    message: str
    recommendations: list[RecommendationCard]


def _fallback_caveat(reception: ReceptionSignal) -> str:
    flag_label = reception.community_flag.value.replace("_", " ")
    if reception.reception_summary:
        return f"Reception is {flag_label}: {reception.reception_summary}"
    return f"Reception is {flag_label} per community sentiment data."


def _build_result(db: Session, respond_input: dict) -> AgentResult:
    recommendations = []
    for rec in respond_input.get("recommendations", []):
        anime = db.get(Anime, rec.get("anime_id"))
        if anime is None:
            continue
        reception = db.get(ReceptionSignal, anime.id)

        caveat = rec.get("caveat")
        # Backstop: don't rely solely on the model remembering to caveat divisive titles --
        # the whole point of check_reception is that this can never be silently skipped.
        if not caveat and reception is not None and reception.community_flag.value != "none":
            caveat = _fallback_caveat(reception)

        recommendations.append(
            RecommendationCard(
                anime_id=anime.id,
                title=anime.title,
                rationale=rec.get("rationale", ""),
                caveat=caveat,
                score=float(anime.score) if anime.score is not None else None,
                community_flag=reception.community_flag.value if reception else None,
                image_url=anime.image_url,
            )
        )
    return AgentResult(message=respond_input.get("message", ""), recommendations=recommendations)


def _condense_history(history: list[dict]) -> list[dict]:
    messages = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        messages.append({"role": "user", "content": turn["query"]})
        recap = turn["message"]
        recs = turn.get("recommendations") or []
        if recs:
            titled = ", ".join(f"{r['title']} (id {r['anime_id']})" for r in recs)
            recap = f"{recap}\n\n(Recommended: {titled})"
        messages.append({"role": "assistant", "content": recap})
    return messages


def _run_tool_round(messages: list, tool_choice: dict | None = None):
    kwargs = {}
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    return client.messages.create(
        model=AGENT_MODEL,
        max_tokens=1500,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=TOOL_DEFINITIONS,
        messages=messages,
        **kwargs,
    )


def run_agent(db: Session, user_query: str, history: list[dict] | None = None) -> AgentResult:
    messages: list = _condense_history(history or [])
    messages.append({"role": "user", "content": user_query})

    for _ in range(MAX_TOOL_ROUNDS):
        response = _run_tool_round(messages)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            messages.append(
                {"role": "user", "content": "Please finalize your answer now by calling the `respond` tool."}
            )
            continue

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        respond_block = next((b for b in tool_use_blocks if b.name == "respond"), None)
        if respond_block is not None:
            return _build_result(db, respond_block.input)

        tool_results = []
        for block in tool_use_blocks:
            try:
                output = execute_tool(db, block.name, block.input)
            except (TypeError, KeyError) as exc:
                output = {"error": f"Invalid arguments for {block.name}: {exc}"}
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output)})
        messages.append({"role": "user", "content": tool_results})

    # Cap reached without a `respond` call -- force finalization.
    messages.append(
        {
            "role": "user",
            "content": (
                "You've reached the tool-call limit. Call `respond` now with your best "
                "recommendations based on everything you've found so far."
            ),
        }
    )
    response = _run_tool_round(messages, tool_choice={"type": "tool", "name": "respond"})
    respond_block = next(b for b in response.content if b.type == "tool_use" and b.name == "respond")
    return _build_result(db, respond_block.input)
