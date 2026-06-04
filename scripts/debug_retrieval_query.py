#!/usr/bin/env python3
"""Explain how a query changes from raw vector matches into a learning path."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine.graph import CurriculumGraph  # noqa: E402
from curriculum_engine.learning_path import build_learning_path_context  # noqa: E402
from curriculum_engine.retrieval import CurriculumRetriever  # noqa: E402
from curriculum_engine.vector_index import (  # noqa: E402
    HFInferenceEmbeddingModel,
    SectionVectorIndex,
)


def load_env_value(path: Path, name: str) -> None:
    if os.environ.get(name) or not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            os.environ[name] = value.strip().strip("\"'")
            return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    load_env_value(args.root / ".env", "HF_TOKEN")
    graph = CurriculumGraph.from_repo(args.root, usable_only=True)
    vector_index = SectionVectorIndex.load(args.root)
    if vector_index is None:
        print("Section vector index is missing.", file=sys.stderr)
        return 1
    vector_index.with_embedding_model(HFInferenceEmbeddingModel())
    documents_by_id = {document.section_id: document for document in vector_index.documents}

    raw = vector_index.search(args.query, subject=args.subject.lower(), limit=args.limit)
    print("RAW VECTOR MATCHES")
    for rank, row in enumerate(raw, start=1):
        print(f"{rank:2}. {row.score:.6f}  {documents_by_id[row.section_id].title}  [{row.section_id}]")

    retriever = CurriculumRetriever(graph, vector_index=vector_index)
    retrieved = retriever.search(
        args.query,
        subject=args.subject.lower(),
        limit=args.limit,
        include_prerequisites=True,
        include_soft_links=True,
    )
    print("\nHYBRID RETRIEVER OUTPUT")
    for rank, row in enumerate(retrieved, start=1):
        print(
            f"{rank:2}. rank={row.ranking_score:8.4f} vector={row.vector_score:.6f} "
            f"evidence={row.evidence_score:6.2f}  {row.title}"
        )
        print(f"    reasons={','.join(row.reasons)} section_id={row.section_id}")

    print("\nTARGET SELECTION TRACE")
    for rank, row in enumerate(retriever.last_selection_trace, start=1):
        print(
            f"{rank:2}. {row['selection_decision']:15} rank={row['ranking_score']:8.4f} "
            f"vector={row['vector_score']:.6f} evidence={row['evidence_score']:6.2f}  {row['title']}"
        )
        if row["rejection_reason"]:
            print(f"    rejected: {row['rejection_reason']}")

    context = build_learning_path_context(graph, retrieved)
    print("\nFINAL LEARNING PATH CONTEXT")
    for bucket_name, rows in (
        ("targets", context.target_sections),
        ("prerequisites", context.prerequisite_sections),
        ("support", context.support_sections),
        ("main_path", context.main_path_sections),
    ):
        print(f"{bucket_name}: {len(rows)}")
        for row in rows:
            print(f"  - {row['title']} [{row['section_id']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
