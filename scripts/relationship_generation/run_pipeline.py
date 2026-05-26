#!/usr/bin/env python3
"""Run the refined relationship-generation pipeline in order."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from common import load_full_chapter, load_manifest, read_json, read_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
ARTIFACT_DIR = REPO_ROOT / "data" / "relationship_artifacts"


STAGES = [
    "03_generate_section_summaries.py",
    "02_normalize_concepts.py",
    "07_gate_relationships.py",
    "08_validate_artifacts.py",
]


def run_stage(stage: str, args: list[str]) -> None:
    cmd = [sys.executable, str(SCRIPT_DIR / stage), *args]
    print(f"\n==> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def scoped_refs(args: argparse.Namespace) -> list:
    grade = int(args.grade) if args.grade else None
    return load_manifest(
        REPO_ROOT / "data/textbook_sources/manifest.json",
        subject=args.subject,
        grade=grade,
        chapter_id=args.chapter_id,
        limit=args.limit,
    )


def expected_sections(refs: list) -> dict[str, set[str]]:
    by_chapter: dict[str, set[str]] = {}
    for ref in refs:
        chapter = load_full_chapter(REPO_ROOT / ref.path)
        by_chapter[ref.id] = {section["id"] for section in chapter["chapter"].get("sections", [])}
    return by_chapter


def require_no_missing(label: str, missing: dict[str, set[str]]) -> None:
    missing = {chapter_id: ids for chapter_id, ids in missing.items() if ids}
    if not missing:
        return
    preview = {
        chapter_id: sorted(ids)[:20]
        for chapter_id, ids in missing.items()
    }
    raise RuntimeError(f"{label} missing expected records: {json.dumps(preview, indent=2)}")


def validate_stage(stage: str, args: argparse.Namespace, refs: list) -> None:
    if not refs:
        raise RuntimeError("No chapters matched the requested filters")

    if stage == "03_generate_section_summaries.py":
        rows = read_jsonl(ARTIFACT_DIR / "section_summaries.jsonl")
        actual_by_chapter: dict[str, set[str]] = {}
        for row in rows:
            actual_by_chapter.setdefault(row.get("chapter_id"), set()).add(row.get("section_id"))
        missing = {
            chapter_id: ids - actual_by_chapter.get(chapter_id, set())
            for chapter_id, ids in expected_sections(refs).items()
        }
        require_no_missing("section summaries", missing)

        concepts = read_jsonl(ARTIFACT_DIR / "raw_concepts.jsonl")
        missing_concepts = {
            ref.id: {ref.id}
            for ref in refs
            if not any(row.get("chapter_id") == ref.id for row in concepts)
        }
        require_no_missing("raw section concepts", missing_concepts)


    elif stage == "07_gate_relationships.py":
        summary = read_json(ARTIFACT_DIR / "relationship_summary.json")
        if summary.get("raw", 0) == 0:
            raise RuntimeError("relationship gating found no raw relationships")

    elif stage == "08_validate_artifacts.py":
        report = read_json(ARTIFACT_DIR / "validation_report.json")
        if report.get("status") != "ok":
            raise RuntimeError(f"artifact validation failed: {report.get('error_count')} errors")
        covered = set(report.get("chapter_coverage", {}))
        missing = {ref.id: {ref.id} for ref in refs if ref.id not in covered}
        require_no_missing("validated chapter coverage", missing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter-id")
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

    refs = scoped_refs(args)
    if not refs:
        raise SystemExit("No chapters matched the requested filters.")

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
        if stage == "03_generate_section_summaries.py":
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
            stage_args = filters[:]

        run_stage(stage, stage_args)
        validate_stage(stage, args, refs)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
