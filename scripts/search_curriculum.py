#!/usr/bin/env python3
"""Search curriculum sections with the hybrid retriever."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph, CurriculumRetriever
from curriculum_engine.vector_index import DEFAULT_MODEL_DIR, SectionVectorIndex, SentenceTransformerEmbeddingModel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--subject")
    parser.add_argument("--grade", type=int)
    parser.add_argument("--chapter-id")
    parser.add_argument("--no-vector", action="store_true")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()

    graph = CurriculumGraph.from_repo(args.root, usable_only=True)
    vector_index = None
    if not args.no_vector:
        vector_index = SectionVectorIndex.load(args.root)
        if vector_index:
            vector_index.with_embedding_model(SentenceTransformerEmbeddingModel(args.model_dir))

    retriever = CurriculumRetriever(graph, vector_index=vector_index)
    results = retriever.search(
        args.query,
        subject=args.subject,
        grade=args.grade,
        chapter_id=args.chapter_id,
        limit=args.limit,
    )
    for row in results:
        print(f"{row.score:6.2f}  {row.section_id}  {row.title}")
        print(f"        reasons={','.join(row.reasons)} concepts={','.join(row.matched_concept_ids[:5])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
