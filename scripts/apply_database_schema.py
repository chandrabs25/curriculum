#!/usr/bin/env python3
"""Apply the idempotent runtime database schema to DATABASE_URL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine.database import database_url, run_schema


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url")
    parser.add_argument(
        "--reset-learning-data",
        action="store_true",
        help="Delete generated plans, module designs, checkpoints, insights, and hotspots before applying the schema",
    )
    args = parser.parse_args()
    url = args.database_url or database_url()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    if args.reset_learning_data:
        run_schema(url, schema_path=ROOT / "database/reset_learning_data.sql")
    run_schema(url, schema_path=ROOT / "database/schema.sql")
    print("database schema applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
