#!/usr/bin/env python3
"""Download the curriculum embedding model into the Hugging Face cache."""

from __future__ import annotations

import argparse
import os

from huggingface_hub import snapshot_download


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--cache-dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    snapshot_path = snapshot_download(
        repo_id=args.model,
        cache_dir=args.cache_dir,
        token=os.getenv("HF_TOKEN") or None,
        force_download=args.force,
    )
    print(snapshot_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
