# AnimeSZN

An agentic RAG application for anime discovery and recommendation. An LLM agent reasons about
a user's request, chooses tools (title search, semantic search, similarity search), and checks
community reception before recommending a title — rather than surfacing anything with a
passable raw score. Full design doc: `Anime RAG Agent/Architecture.md` (Obsidian).

**Status:** data pipeline in progress. Metadata ingestion from Jikan is working; embeddings,
review summarization, the agent loop, API, and frontend are not built yet.

## Requirements

- Python 3.11+
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension
- Redis (for the ingestion/embedding job queue — not wired up yet)
- Anthropic API key, Voyage AI API key (needed once the agent/embedding stages are built)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL to your local Postgres user/db, add API keys

createdb anime_szn
psql -d anime_szn -c "CREATE EXTENSION vector;"
alembic upgrade head
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

## Ingestion

Fetches anime metadata from the [Jikan API](https://docs.api.jikan.moe/) (unofficial MAL API),
transforms it, and upserts into Postgres. Idempotent — safe to re-run.

```bash
python -m ingestion.ingest                  # full catalog
python -m ingestion.ingest --max-pages 5    # limited run for testing (25 entries/page)
```

This does **not** generate embeddings or pull reviews yet — that's the next build stage.

## Project layout

```
app/            # FastAPI live app (models, config, db session)
ingestion/      # offline batch pipeline: fetch -> transform -> load (Jikan)
migrations/     # Alembic schema migrations
tests/
```
