# AnimeSZN

An agentic RAG application for anime discovery and recommendation. An LLM agent reasons about
a user's request, chooses tools (title search, semantic search, similarity search), and checks
community reception before recommending a title — rather than surfacing anything with a
passable raw score. Full design doc: `Anime RAG Agent/Architecture.md` (Obsidian).

**Status:** full pipeline working end-to-end (ingestion → embeddings → review summarization →
agent → API → frontend). Full Jikan catalog ingested: ~30,200 titles, all with embeddings and
poster images. Review summarization (reception data) is still only populated for the original
~25-title seed set — see [Known gaps](#known-gaps--next-steps).

## Requirements

- Python 3.11+, Node 18+
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension
- Redis (for background job queueing — batch scripts currently run synchronously via CLI, not yet wired through RQ)
- Anthropic API key (with billing/credits enabled) and Voyage AI API key

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL to your local Postgres user/db, add ANTHROPIC_API_KEY and VOYAGE_API_KEY

createdb anime_szn
psql -d anime_szn -c "CREATE EXTENSION vector;"
alembic upgrade head

cd frontend
npm install
```

If `CREATE EXTENSION vector` fails with "extension is not available," pgvector isn't installed
against your Postgres build. `brew install pgvector` only ships bottles for the newest one or two
Postgres major versions — if you're on an older major version, build it from source:

```bash
git clone --branch v0.8.4 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=$(brew --prefix postgresql@16)/bin/pg_config
make install PG_CONFIG=$(brew --prefix postgresql@16)/bin/pg_config
```

## Running it

```bash
# backend, from repo root
source venv/bin/activate
uvicorn app.main:app --port 8000

# frontend, in another terminal
cd frontend
npm run dev   # http://localhost:5173
```

## Data pipeline (offline/batch, run in this order)

All idempotent — safe to re-run; each only processes rows missing that stage's output.

```bash
# 1. Metadata: fetch from Jikan, transform, upsert
python -m ingestion.ingest                  # full catalog (rate-limited, ~1 req/sec, slow)
python -m ingestion.ingest --max-pages 5    # limited run for testing (25 entries/page)

# 2. Embeddings: Voyage AI, synopsis + genres/tags -> pgvector column
python -m ingestion.embed

# 3. Validate retrieval quality before trusting the agent's tool results
python -m tests.eval.run_eval

# 4. Review summarization: Jikan reviews -> Claude Haiku (Batch API) -> reception_signals
python -m ingestion.summarize_reception
# if it times out waiting on the batch, resume later:
python -m ingestion.summarize_reception --resume <batch_id>
```

## Agent

`app/agent/loop.py` runs the tool-use loop (capped at 3 tool-call rounds, then a forced
`respond` call) using `search_by_title`, `semantic_search`, `find_similar`, `check_reception`,
and a final `respond` tool that the model must call to structure its answer.
Reception caveats are backstopped in code (`_fallback_caveat`) — if the model recommends a
`mixed`/`widely_criticized` title without writing a caveat itself, one is generated from the
stored reception summary so a divisive title is never surfaced silently.

## API

- `POST /recommend` — `{"query": "..."}` → agent message + structured recommendation cards
- `GET /anime/{id}` — full metadata + reception summary for a single title

## Project structure

```
app/                        # FastAPI live app
├── main.py                 # app instance, CORS, router registration
├── config.py                # env-driven settings (pydantic-settings)
├── db.py                    # SQLAlchemy engine/session
├── schemas.py                # Pydantic request/response models
├── search.py                 # semantic_search + popularity-aware reranking
├── embeddings.py             # Voyage AI client (shared by app + ingestion)
├── llm.py                    # Anthropic client + model ids (shared by app + ingestion)
├── jikan_client.py           # live, on-demand Jikan calls (streaming lookup) -- retried, no rate-limit pacing
├── models/
│   ├── anime.py               # `anime` table (metadata + pgvector embedding column)
│   └── reception.py           # `reception_signals` table
├── agent/
│   ├── loop.py                # tool-use loop, system prompt(s), multi-turn history, spoiler mode
│   └── tools.py               # tool definitions + executors (search_by_title, semantic_search, find_similar, check_reception, respond)
└── routers/
    ├── recommend.py            # POST /recommend
    ├── anime.py                 # GET /anime/{id}
    └── discover.py               # GET /discover (homepage "airing now")

ingestion/                  # offline batch pipeline (fetch -> transform -> load -> embed -> summarize)
├── jikan_client.py          # rate-limited bulk Jikan client (retried), separate from app/jikan_client.py
├── transform.py              # Jikan response -> DB row
├── load.py                   # idempotent upsert
├── ingest.py                  # full/partial catalog crawl (CLI)
├── embed.py                   # Voyage embedding backfill (CLI)
└── summarize_reception.py      # Claude Haiku batch review summarization (CLI)

migrations/                 # Alembic schema migrations
tests/eval/                 # retrieval-quality eval set + runner (validates semantic_search before trusting the agent)
frontend/                   # React (Vite)
└── src/
    ├── App.jsx               # query box, chat thread, discovery grid, spotlight/grid cards, spoiler toggle
    ├── App.css                # dark theme, animations, all component styling
    └── index.css               # fonts, CSS variables, base reset
```

## Known gaps / next steps

- **No scheduled catalog refresh.** Ingestion/embeddings/reception are only ever run manually —
  there's no cron/launchd job or RQ/Redis schedule re-running them (e.g. weekly/monthly, as the
  original architecture doc intended). The catalog is a static snapshot from whenever someone
  last ran `ingestion/ingest.py` by hand; new releases, score changes, and status transitions
  (e.g. airing → finished) won't show up until it's manually re-run.
- Review summarization (`ingestion/summarize_reception.py`) has only been run for the original
  ~25-title seed set, not the full ~30K catalog (~$25 est. cost, ~8hr wall-clock — see git log
  for the cost breakdown). Until it's run at full scale, `check_reception` has no real data for
  most titles, so the agent's reception commentary on those is unverified model knowledge, not
  the sourced signal the whole project is built around.
- RQ/Redis job queue not wired up — batch scripts run directly via CLI (same root cause as the
  scheduling gap above)
- `search_by_title` uses plain `ILIKE`, not proper fuzzy matching (e.g. pg_trgm)
- No automated tests beyond the retrieval eval
