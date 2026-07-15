"""Offline batch job: fetch anime metadata from AniList, transform, and load into Postgres.

Run: python -m ingestion.ingest [--batch-size N] [--start-year N]

Idempotent — safe to re-run; existing rows are upserted by AniList id. Use --start-year to
resume a long crawl (the crawl is sliced year by year to work around AniList's 5000-entry
pagination cap) without re-fetching years already loaded. Always finishes with a pass that
converts AniList's raw popularity counts into ranks across the whole table.
Embeddings and review summarization are separate later-stage jobs, not run here.
"""

import argparse
import logging

from app.db import SessionLocal
from ingestion.anilist_client import EARLIEST_YEAR, iter_anime
from ingestion.load import finalize_popularity_ranks, upsert_anime
from ingestion.transform import transform_anime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(batch_size: int, start_year: int) -> None:
    db = SessionLocal()
    batch: list[dict] = []
    total = 0
    try:
        for entry in iter_anime(start_year=start_year):
            try:
                batch.append(transform_anime(entry))
            except KeyError as exc:
                logger.warning("Skipping entry %s, missing field %s", entry.get("id"), exc)
                continue

            if len(batch) >= batch_size:
                try:
                    upsert_anime(db, batch)
                    total += len(batch)
                    logger.info("Upserted %d anime so far", total)
                except Exception:
                    db.rollback()
                    logger.exception("Failed to upsert batch (ids %s) -- skipping and continuing", [r["id"] for r in batch])
                batch = []

        if batch:
            try:
                upsert_anime(db, batch)
                total += len(batch)
            except Exception:
                db.rollback()
                logger.exception("Failed to upsert final batch (ids %s)", [r["id"] for r in batch])

        logger.info("Done. Upserted %d anime total. Finalizing popularity ranks...", total)
        finalize_popularity_ranks(db)
        logger.info("Popularity ranks finalized.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=25, help="Rows per upsert batch")
    parser.add_argument("--start-year", type=int, default=EARLIEST_YEAR, help="Resume the crawl from this year")
    args = parser.parse_args()
    run(batch_size=args.batch_size, start_year=args.start_year)
