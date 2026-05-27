#!/usr/bin/env python3
"""Build the local section-level vector index for curriculum retrieval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph
from curriculum_engine.vector_index import (
    DEFAULT_INDEX_DIR,
    DEFAULT_MODEL_DIR,
    SentenceTransformerEmbeddingModel,
    build_section_documents,
    write_vector_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--include-partial", action="store_true", help="Index all artifact rows, not only usable chapters.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else args.root / args.output_dir
    graph = CurriculumGraph.from_repo(args.root, usable_only=not args.include_partial)
    documents = build_section_documents(graph)
    if not documents:
        print("No section documents found for retrieval indexing.", file=sys.stderr)
        return 1
    model = SentenceTransformerEmbeddingModel(args.model_dir)
    manifest = write_vector_index(
        documents,
        model,
        output_dir=output_dir,
        model_dir=args.model_dir,
        force=args.force,
    )
    print(
        f"wrote retrieval index: {manifest['document_count']} documents, "
        f"{manifest['embedding_dimension']} dimensions -> {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
