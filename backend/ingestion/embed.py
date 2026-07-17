"""Offline batch job: generate synopsis+tag embeddings for anime rows missing them.

Run: python -m ingestion.embed [--batch-size N] [--reembed-all]

Idempotent by default — only embeds rows where synopsis_embedding IS NULL.
Pass --reembed-all to regenerate embeddings for every row (e.g. after a model change).
"""

import argparse
import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.embeddings import MAX_BATCH_SIZE, build_embedding_text, embed_documents
from app.models.anime import Anime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# Finds anime rows needing embeddings (all rows if --reembed-all), embeds them in batches, and
# commits incrementally so a mid-run failure doesn't lose already-embedded rows.
def run(batch_size: int, reembed_all: bool) -> None:
    db = SessionLocal()
    try:
        query = select(Anime)
        if not reembed_all:
            query = query.where(Anime.synopsis_embedding.is_(None))
        rows = db.scalars(query).all()

        if not rows:
            logger.info("Nothing to embed.")
            return

        logger.info("Embedding %d anime", len(rows))
        total = 0
        for i in range(0, len(rows), batch_size):
            chunk = rows[i : i + batch_size]
            texts = [build_embedding_text(r.title, r.synopsis, r.genres, r.tags) for r in chunk]
            try:
                vectors = embed_documents(texts)
            except Exception:
                logger.exception("Failed to embed batch (ids %s) -- skipping and continuing", [r.id for r in chunk])
                continue
            for row, vector in zip(chunk, vectors):
                row.synopsis_embedding = vector
            db.commit()
            total += len(chunk)
            logger.info("Embedded %d/%d", total, len(rows))

        logger.info("Done. Embedded %d anime total.", total)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH_SIZE)
    parser.add_argument("--reembed-all", action="store_true")
    args = parser.parse_args()
    run(batch_size=args.batch_size, reembed_all=args.reembed_all)
