"""Offline batch job: fetch anime metadata from Jikan, transform, and load into Postgres.

Run: python -m ingestion.ingest [--max-pages N] [--batch-size N]

Idempotent — safe to re-run; existing rows are upserted by MAL id.
Embeddings and review summarization are separate later-stage jobs, not run here.
"""

import argparse
import logging

from app.db import SessionLocal
from ingestion.jikan_client import iter_anime
from ingestion.load import upsert_anime
from ingestion.transform import transform_anime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(max_pages: int | None, batch_size: int) -> None:
    db = SessionLocal()
    batch: list[dict] = []
    total = 0
    try:
        for entry in iter_anime(max_pages=max_pages):
            try:
                batch.append(transform_anime(entry))
            except KeyError as exc:
                logger.warning("Skipping entry %s, missing field %s", entry.get("mal_id"), exc)
                continue

            if len(batch) >= batch_size:
                upsert_anime(db, batch)
                total += len(batch)
                logger.info("Upserted %d anime so far", total)
                batch = []

        if batch:
            upsert_anime(db, batch)
            total += len(batch)

        logger.info("Done. Upserted %d anime total.", total)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=None, help="Limit pages fetched (25 entries/page)")
    parser.add_argument("--batch-size", type=int, default=25, help="Rows per upsert batch")
    args = parser.parse_args()
    run(max_pages=args.max_pages, batch_size=args.batch_size)
