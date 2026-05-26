#!/usr/bin/env python3
"""Run the refined relationship-generation pipeline in order."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


STAGES = [
    "01_extract_chapter_concepts.py",
    "02_normalize_concepts.py",
    "03_generate_unit_summaries.py",
    "04_generate_unit_concept_edges.py",
    "05_generate_unit_dependencies.py",
    "06_generate_exercise_edges.py",
    "07_gate_relationships.py",
    "08_validate_artifacts.py",
]


def run_stage(stage: str, args: list[str]) -> None:
    cmd = [sys.executable, str(SCRIPT_DIR / stage), *args]
    print(f"\n==> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter-id", default="ncert:physics:11:1")
    parser.add_argument("--subject", choices=["physics", "chemistry", "biology"])
    parser.add_argument("--grade", choices=["11", "12"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-gemini-adjudication", action="store_true")
    parser.add_argument("--start-at", choices=STAGES, default=STAGES[0])
    parser.add_argument("--stop-after", choices=STAGES)
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit(
            "GEMINI_API_KEY is not set. Run: export GEMINI_API_KEY='...'\n"
            "Tip: rotate any key that has been pasted into terminal logs or chat."
        )

    filters: list[str] = []
    if args.chapter_id:
        filters += ["--chapter-id", args.chapter_id]
    if args.subject:
        filters += ["--subject", args.subject]
    if args.grade:
        filters += ["--grade", args.grade]
    if args.limit is not None:
        filters += ["--limit", str(args.limit)]
    if args.model:
        filters += ["--model", args.model]
    if args.force:
        filters.append("--force")

    start_index = STAGES.index(args.start_at)
    stop_index = STAGES.index(args.stop_after) if args.stop_after else len(STAGES) - 1

    for stage in STAGES[start_index : stop_index + 1]:
        stage_args: list[str] = []
        if stage in {
            "01_extract_chapter_concepts.py",
            "03_generate_unit_summaries.py",
            "04_generate_unit_concept_edges.py",
            "05_generate_unit_dependencies.py",
            "06_generate_exercise_edges.py",
        }:
            stage_args = filters[:]
        elif stage == "02_normalize_concepts.py":
            if args.model:
                stage_args += ["--model", args.model]
            if args.force:
                stage_args.append("--force")
            if not args.skip_gemini_adjudication:
                stage_args.append("--use-gemini-adjudication")
        elif stage == "07_gate_relationships.py":
            if args.force:
                stage_args.append("--force")
        elif stage == "08_validate_artifacts.py":
            stage_args = []

        run_stage(stage, stage_args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
