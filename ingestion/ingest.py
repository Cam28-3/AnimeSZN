"""Offline batch job: fetch anime metadata from Jikan, transform, and load into Postgres.

Run: python -m ingestion.ingest [--max-pages N] [--batch-size N] [--start-page N]

Idempotent — safe to re-run; existing rows are upserted by MAL id. Use --start-page to
resume a long crawl (25 entries/page) without re-fetching pages already loaded.
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


def run(max_pages: int | None, batch_size: int, start_page: int) -> None:
    db = SessionLocal()
    batch: list[dict] = []
    total = 0
    try:
        for entry in iter_anime(max_pages=max_pages, start_page=start_page):
            try:
                batch.append(transform_anime(entry))
            except KeyError as exc:
                logger.warning("Skipping entry %s, missing field %s", entry.get("mal_id"), exc)
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

        logger.info("Done. Upserted %d anime total.", total)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=None, help="Limit pages fetched (25 entries/page)")
    parser.add_argument("--batch-size", type=int, default=25, help="Rows per upsert batch")
    parser.add_argument("--start-page", type=int, default=1, help="Resume from this Jikan page (25 entries/page)")
    args = parser.parse_args()
    run(max_pages=args.max_pages, batch_size=args.batch_size, start_page=args.start_page)
