# AnimeSZN

An agentic RAG application for anime discovery and recommendation. An LLM agent reasons about
a user's request, chooses tools (title search, semantic search, similarity search), and checks
community reception before recommending a title — rather than surfacing anything with a
passable raw score. Full design doc: `Anime RAG Agent/Architecture.md` (Obsidian).

**Status:** full pipeline working end-to-end (ingestion → embeddings → review summarization →
agent → API → frontend) against a small ~25-title test catalog. The full Jikan catalog pull
hasn't been run yet — see [Ingestion](#ingestion).

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

## Project layout

```
app/            # FastAPI live app: models, config, db session, search, embeddings, llm client, agent, routers
ingestion/      # offline batch pipeline: fetch -> transform -> load -> embed -> summarize (Jikan + Voyage + Haiku)
migrations/     # Alembic schema migrations
tests/eval/     # retrieval-quality eval set + runner
frontend/       # React (Vite) — query box + recommendation cards
```

## Known gaps / next steps

- Full Jikan catalog hasn't been ingested yet (currently ~25 titles); eval set and agent
  behavior should be re-validated at full scale
- RQ/Redis job queue not wired up — batch scripts run directly via CLI
- `search_by_title` uses plain `ILIKE`, not proper fuzzy matching (e.g. pg_trgm)
- No automated tests beyond the retrieval eval
