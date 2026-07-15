"""Retrieval quality eval for bare semantic_search, run before wrapping it in the agent loop.

Run: python -m tests.eval.run_eval [--k 3]

Checks whether the expected anime appears in the top-k results for each hand-written query.
This eval set is small and scoped to the ~25 titles currently ingested — re-expand it once
the full AniList catalog is loaded.
"""

import argparse
import json
from pathlib import Path

from app.db import SessionLocal
from app.embeddings import embed_queries
from app.search import SearchFilters, semantic_search_by_vector

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"


def run(k: int) -> None:
    cases = json.loads(EVAL_SET_PATH.read_text())
    query_vectors = embed_queries([case["query"] for case in cases])  # one request, avoids per-call rate limits
    db = SessionLocal()
    hits = 0
    try:
        for case, query_vector in zip(cases, query_vectors):
            results = semantic_search_by_vector(db, query_vector, filters=SearchFilters(), limit=k)
            result_ids = [r.id for r in results]
            hit = case["expected_id"] in result_ids
            hits += hit
            status = "PASS" if hit else "FAIL"
            top_titles = ", ".join(f"{r.title} ({r.similarity:.3f})" for r in results)
            print(f"[{status}] expected={case['expected_title']!r:45} top-{k}: {top_titles}")
    finally:
        db.close()

    print(f"\n{hits}/{len(cases)} passed (top-{k} hit rate)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    run(k=args.k)
