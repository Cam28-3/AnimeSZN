"""Offline batch job: summarize review reception per anime using Claude Haiku (Batch API).

Run: python -m ingestion.summarize_reception [--max-reviews N] [--reprocess-all]
     python -m ingestion.summarize_reception --resume <batch_id>

Fetches sampled reviews from AniList, sends them to Claude Haiku via the Message Batches API
to produce a short reception summary + sentiment ratio, and upserts into reception_signals.
Idempotent — only processes anime missing a reception_signals row unless --reprocess-all.

The Batch API is async (can take minutes to hours). If it hasn't finished by --poll-timeout,
the batch id is printed so the job can be resumed later with --resume.

The review-fetch phase (before batch submission) can take many hours for a full catalog and
checkpoints its progress to .reception_fetch_checkpoint.jsonl -- if the process is interrupted
before a batch is submitted, just re-run the same command and it picks up where it left off
instead of re-fetching everything.
"""

import argparse
import json
import logging
import time
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.llm import SUMMARIZATION_MODEL, client
from app.models.anime import Anime
from app.models.reception import CommunityFlag, ReceptionSignal
from ingestion.anilist_client import fetch_reviews
from ingestion.transform import clean_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_REVIEW_CHARS = 600
# The fetch phase can take many hours for a full catalog; this checkpoint lets a restart skip
# titles already fetched instead of redoing the whole (free but slow) AniList crawl. Cleared
# once a batch is successfully submitted -- from that point on, --resume <batch_id> is the
# right recovery path, not the checkpoint.
CHECKPOINT_PATH = Path(__file__).parent / ".reception_fetch_checkpoint.jsonl"
SYSTEM_PROMPT = (
    "You analyze anime fan reviews to summarize community reception. "
    "Given the anime title and a sample of user reviews, respond with ONLY a JSON object "
    '(no other text) of the form {"summary": "...", "sentiment_ratio": 0.0} where summary is '
    "a 1-2 sentence human-readable description of overall reception (mention notable praise "
    "or criticism), and sentiment_ratio is a float from 0.0 (entirely negative) to 1.0 "
    "(entirely positive) reflecting the balance of positive vs negative sentiment."
)


# Maps Haiku's sentiment_ratio score onto the CommunityFlag enum the agent's check_reception
# tool surfaces -- this is what actually triggers the "never recommend silently" behavior.
def derive_community_flag(sentiment_ratio: float | None) -> CommunityFlag:
    if sentiment_ratio is None:
        return CommunityFlag.none
    if sentiment_ratio < 0.4:
        return CommunityFlag.widely_criticized
    if sentiment_ratio < 0.6:
        return CommunityFlag.mixed
    return CommunityFlag.none


# Builds one Message Batches API request entry for a title -- custom_id is the anime_id so
# apply_batch_results can map results back to rows.
def build_batch_request(anime_id: int, title: str, reviews: list[str]) -> dict:
    review_text = "\n\n".join(f"Review {i+1}: {r[:MAX_REVIEW_CHARS]}" for i, r in enumerate(reviews))
    return {
        "custom_id": str(anime_id),
        "params": {
            "model": SUMMARIZATION_MODEL,
            "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": f"Anime: {title}\n\n{review_text}"}],
        },
    }


# Writes (or updates) one anime's reception_signals row from a summary/sentiment_ratio pair.
def upsert_reception(db, anime_id: int, summary: str | None, sentiment_ratio: float | None) -> None:
    flag = derive_community_flag(sentiment_ratio)
    existing = db.get(ReceptionSignal, anime_id)
    if existing:
        existing.reception_summary = summary
        existing.review_sentiment_ratio = sentiment_ratio
        existing.community_flag = flag
    else:
        db.add(
            ReceptionSignal(
                anime_id=anime_id,
                reception_summary=summary,
                review_sentiment_ratio=sentiment_ratio,
                community_flag=flag,
            )
        )


# Fetches and cleans review text for one title, dropping any reviews that end up empty after
# HTML-stripping.
def collect_review_texts(anime_id: int, max_reviews: int) -> list[str]:
    raw_reviews = fetch_reviews(anime_id, max_reviews=max_reviews)
    cleaned = [clean_text(r) for r in raw_reviews]
    return [r for r in cleaned if r]


# Loads already-fetched titles from a prior interrupted run. Only successful fetches are
# checkpointed (see fetch_all_reviews), so permanently-failed titles are naturally retried.
def load_checkpoint() -> dict[int, list[str]]:
    if not CHECKPOINT_PATH.exists():
        return {}
    checkpoint = {}
    with CHECKPOINT_PATH.open() as f:
        for line in f:
            entry = json.loads(line)
            checkpoint[entry["anime_id"]] = entry["reviews"]
    return checkpoint


def append_checkpoint(anime_id: int, reviews: list[str]) -> None:
    with CHECKPOINT_PATH.open("a") as f:
        f.write(json.dumps({"anime_id": anime_id, "reviews": reviews}) + "\n")


def clear_checkpoint() -> None:
    CHECKPOINT_PATH.unlink(missing_ok=True)


# Submits the whole set of per-title requests as one async Anthropic Message Batch job.
def submit_batch(requests: list[dict]) -> str:
    batch = client.messages.batches.create(requests=requests)
    logger.info("Submitted batch %s with %d requests", batch.id, len(requests))
    return batch.id


def poll_batch(batch_id: str, poll_interval: int, poll_timeout: int) -> bool:
    """Returns True if the batch ended within the timeout."""
    waited = 0
    while waited <= poll_timeout:
        batch = client.messages.batches.retrieve(batch_id)
        logger.info("Batch %s status: %s", batch_id, batch.processing_status)
        if batch.processing_status == "ended":
            return True
        time.sleep(poll_interval)
        waited += poll_interval
    return False


def extract_json(raw_text: str) -> dict:
    """Haiku sometimes wraps JSON in a markdown code fence despite instructions not to."""
    start, end = raw_text.find("{"), raw_text.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("No JSON object found", raw_text, 0)
    return json.loads(raw_text[start : end + 1])


# Walks a finished batch's results, parses each Haiku response, and upserts reception_signals
# rows -- skips (with a warning, not a crash) any entry that failed or came back unparseable.
def apply_batch_results(db, batch_id: str) -> int:
    processed = 0
    for result in client.messages.batches.results(batch_id):
        anime_id = int(result.custom_id)
        if result.result.type != "succeeded":
            logger.warning("Batch entry %s did not succeed: %s", anime_id, result.result.type)
            continue
        message = result.result.message
        raw_text = "".join(block.text for block in message.content if block.type == "text")
        try:
            parsed = extract_json(raw_text)
            upsert_reception(db, anime_id, parsed.get("summary"), parsed.get("sentiment_ratio"))
            processed += 1
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse result for anime %s: %s", anime_id, exc)
    db.commit()
    return processed


def fetch_all_reviews(rows: list[Anime], max_reviews: int) -> tuple[list[dict], list[int]]:
    """Returns (batch_requests, no_review_ids). Titles that fail permanently (retries
    exhausted) are logged and skipped rather than aborting the whole run -- they have no
    reception_signals row written, so the idempotent query above picks them back up next time.
    Already-fetched titles from a prior interrupted run are loaded from CHECKPOINT_PATH and
    skipped; newly-fetched titles are appended to it as they complete, so a crash mid-run only
    costs the titles fetched since the last checkpoint write, not the whole run."""
    checkpoint = load_checkpoint()
    if checkpoint:
        logger.info("Resuming from checkpoint: %d titles already fetched", len(checkpoint))

    batch_requests = []
    no_review_ids = []
    skipped_count = 0
    resumed_count = 0
    for i, row in enumerate(rows, start=1):
        if row.id in checkpoint:
            reviews = checkpoint[row.id]
            resumed_count += 1
        else:
            try:
                reviews = collect_review_texts(row.id, max_reviews)
            except Exception:
                logger.exception("Giving up on anime %s after retries -- skipping", row.id)
                skipped_count += 1
                continue
            append_checkpoint(row.id, reviews)

        if reviews:
            batch_requests.append(build_batch_request(row.id, row.title, reviews))
        else:
            no_review_ids.append(row.id)
        if i % 250 == 0:
            logger.info(
                "Progress: %d/%d anime processed (%d skipped, %d resumed from checkpoint)",
                i, len(rows), skipped_count, resumed_count,
            )
    return batch_requests, no_review_ids


# Orchestrates the full job: resume-mode just polls/applies an existing batch; otherwise finds
# anime missing reception data, fetches reviews, submits a Haiku batch, and applies results
# (or prints --resume instructions if the batch is still running at --poll-timeout).
def run(max_reviews: int, reprocess_all: bool, poll_interval: int, poll_timeout: int, resume_batch_id: str | None) -> None:
    db = SessionLocal()
    try:
        if resume_batch_id:
            ended = poll_batch(resume_batch_id, poll_interval, poll_timeout)
            if not ended:
                logger.info("Batch %s still not finished. Re-run with --resume %s later.", resume_batch_id, resume_batch_id)
                return
            processed = apply_batch_results(db, resume_batch_id)
            logger.info("Applied %d reception summaries from batch %s.", processed, resume_batch_id)
            return

        query = select(Anime)
        if not reprocess_all:
            query = query.outerjoin(ReceptionSignal, ReceptionSignal.anime_id == Anime.id).where(
                ReceptionSignal.anime_id.is_(None)
            )
        rows = db.scalars(query).all()

        if not rows:
            logger.info("Nothing to summarize.")
            return

        logger.info("Fetching reviews for %d anime from AniList (rate-limited, this is slow)...", len(rows))
        batch_requests, no_review_ids = fetch_all_reviews(rows, max_reviews)

        for anime_id in no_review_ids:
            upsert_reception(db, anime_id, summary=None, sentiment_ratio=None)
        db.commit()
        logger.info("%d anime had no reviews; recorded with no reception data.", len(no_review_ids))

        if not batch_requests:
            logger.info("No batch requests to submit.")
            clear_checkpoint()  # fetch phase is fully done, nothing left for it to protect
            return

        batch_id = submit_batch(batch_requests)
        # From here on, --resume <batch_id> is the recovery path (the batch lives on
        # Anthropic's servers independent of this process) -- the checkpoint's job is done.
        clear_checkpoint()
        ended = poll_batch(batch_id, poll_interval, poll_timeout)
        if not ended:
            logger.info("Batch %s still processing. Re-run with --resume %s to finish later.", batch_id, batch_id)
            return

        processed = apply_batch_results(db, batch_id)
        logger.info("Done. Applied %d reception summaries.", processed)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-reviews", type=int, default=6)
    parser.add_argument("--reprocess-all", action="store_true")
    parser.add_argument("--poll-interval", type=int, default=15, help="Seconds between batch status checks")
    parser.add_argument("--poll-timeout", type=int, default=600, help="Max seconds to wait before giving up and printing --resume instructions")
    parser.add_argument("--resume", dest="resume_batch_id", default=None, help="Resume polling/applying an existing batch id")
    args = parser.parse_args()
    run(
        max_reviews=args.max_reviews,
        reprocess_all=args.reprocess_all,
        poll_interval=args.poll_interval,
        poll_timeout=args.poll_timeout,
        resume_batch_id=args.resume_batch_id,
    )
