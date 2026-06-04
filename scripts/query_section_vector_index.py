#!/usr/bin/env python3
"""Query the local section vector index and print the top matching sections."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine.vector_index import (  # noqa: E402
    DEFAULT_INDEX_DIR,
    DEFAULT_MODEL_DIR,
    HFInferenceEmbeddingModel,
    SectionVectorIndex,
    SentenceTransformerEmbeddingModel,
)


def load_env_value(path: Path, name: str) -> None:
    """Load one missing environment variable from a simple .env file."""
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
    parser.add_argument("query", help="Natural-language query to embed and search.")
    parser.add_argument("--subject", required=True, help="Subject filter, such as physics.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--grade", type=int)
    parser.add_argument("--chapter-id")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument(
        "--embedding-backend",
        choices=("hf-api", "local"),
        default="hf-api",
        help="Embed the query through Hugging Face Inference API or a local model.",
    )
    parser.add_argument("--hf-model", default="BAAI/bge-m3")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()
    load_env_value(args.root / ".env", "HF_TOKEN")

    index = SectionVectorIndex.load(args.root, index_dir=args.index_dir)
    if index is None:
        print(f"Section vector index not found under {args.root / args.index_dir}", file=sys.stderr)
        return 1

    if args.embedding_backend == "hf-api":
        embedding_model = HFInferenceEmbeddingModel(model=args.hf_model)
    else:
        embedding_model = SentenceTransformerEmbeddingModel(args.model_dir)
    index.with_embedding_model(embedding_model)
    documents_by_id = {document.section_id: document for document in index.documents}
    try:
        results = index.search(
            args.query,
            subject=args.subject.strip().lower(),
            grade=args.grade,
            chapter_id=args.chapter_id,
            limit=max(1, args.limit),
        )
    except Exception as exc:
        if args.embedding_backend == "hf-api" and "401 Unauthorized" in str(exc):
            print(
                "Hugging Face Inference API rejected the request. "
                "Set HF_TOKEN or add it to the repo root .env file.",
                file=sys.stderr,
            )
            return 1
        raise

    if not results:
        print("No matching sections found.", file=sys.stderr)
        return 1

    for rank, result in enumerate(results, start=1):
        document = documents_by_id[result.section_id]
        print(f"{rank}. {document.title}")
        print(f"   score={result.score:.6f} section_id={result.section_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
