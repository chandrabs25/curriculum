#!/usr/bin/env python3
"""Extract content-only textbook source JSON from LearnerOS chapter files.

The source LearnerOS JSON files contain useful textbook structure plus
relationship-like fields that were generated for a different graph model.
This extractor preserves the textbook content and stable identifiers, while
removing relationship fields such as section prerequisites and exercise tests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_DIR = Path("/Users/srichandrasamanapalli/code/AI TUTOR/learneros/data")
DEFAULT_OUTPUT_DIR = Path("data/textbook_sources")
MANIFEST_NAME = "manifest.json"


def stable_prefix(raw: dict[str, Any]) -> str:
    chapter = raw["chapter"]
    return f"{raw['curriculum']}:{raw['subject']}:{raw['grade']}:{chapter['number']}"


def clean_table(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": table.get("label"),
        "caption": table.get("caption"),
        "headers": table.get("headers") or [],
        "rows": table.get("rows") or [],
    }


def clean_subsection(section_id: str, subsection: dict[str, Any]) -> dict[str, Any]:
    subsection_id = f"{section_id}:{subsection['order']}"
    return {
        "id": subsection_id,
        "order": subsection.get("order"),
        "title": subsection.get("title") or "",
        "content_text": subsection.get("content_text") or "",
        "content_type": subsection.get("content_type") or "explanation",
        "worked_examples": [
            {
                "label": item.get("label"),
                "problem": item.get("problem") or "",
                "solution": item.get("solution"),
            }
            for item in subsection.get("worked_examples") or []
        ],
        "diagrams": [
            {
                "label": item.get("label"),
                "description": item.get("description") or "",
                "image_url": item.get("image_url"),
            }
            for item in subsection.get("diagrams") or []
        ],
        "tables": [clean_table(item) for item in subsection.get("tables") or []],
    }


def clean_section(chapter_prefix: str, section: dict[str, Any]) -> dict[str, Any]:
    section_id = f"{chapter_prefix}:{section['number']}"
    return {
        "id": section_id,
        "number": section.get("number"),
        "title": section.get("title") or "",
        "content_text": section.get("content_text") or "",
        "subsections": [
            clean_subsection(section_id, subsection)
            for subsection in section.get("subsections") or []
        ],
    }


def clean_exercise(chapter_prefix: str, exercise: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{chapter_prefix}:ex:{exercise['number']}",
        "number": exercise.get("number"),
        "problem": exercise.get("problem") or "",
        "solution": exercise.get("solution"),
        "difficulty": exercise.get("difficulty"),
        "exercise_type": exercise.get("exercise_type"),
    }


def clean_chapter(raw: dict[str, Any], source_file: Path) -> dict[str, Any]:
    chapter = raw["chapter"]
    chapter_prefix = stable_prefix(raw)
    exercises = chapter.get("exercises") or {}
    return {
        "schema_version": "textbook_source.v1",
        "source": {
            "repository": "learneros",
            "source_file": str(source_file),
            "relationship_fields_removed": ["chapter.sections[].prerequisites", "chapter.exercises.items[].tests"],
        },
        "id": chapter_prefix,
        "curriculum": raw.get("curriculum"),
        "subject": raw.get("subject"),
        "grade": raw.get("grade"),
        "textbook_name": raw.get("textbook_name"),
        "volume": raw.get("volume"),
        "chapter": {
            "id": chapter_prefix,
            "number": chapter.get("number"),
            "title": chapter.get("title") or "",
            "summary": chapter.get("summary") or "",
            "sections": [
                clean_section(chapter_prefix, section)
                for section in chapter.get("sections") or []
                if section.get("number") is not None
            ],
            "exercises": {
                "title": exercises.get("title") or "Exercises",
                "items": [
                    clean_exercise(chapter_prefix, item)
                    for item in exercises.get("items") or []
                    if item.get("number") is not None
                ],
            },
        },
    }


def output_path_for(cleaned: dict[str, Any], output_dir: Path) -> Path:
    subject = cleaned["subject"]
    grade = cleaned["grade"]
    chapter_number = cleaned["chapter"]["number"]
    filename = f"{cleaned['curriculum']}_{subject}_{grade}_ch{chapter_number}.json"
    return output_dir / subject / f"grade_{grade}" / filename


def iter_source_files(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.glob("ncert_*.json")
        if not path.name.endswith(".raw.json")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    source_files = iter_source_files(args.source_dir)
    if not source_files:
        raise SystemExit(f"No source files found in {args.source_dir}")

    manifest: list[dict[str, Any]] = []
    for source_file in source_files:
        raw = json.loads(source_file.read_text(encoding="utf-8"))
        cleaned = clean_chapter(raw, source_file)
        target = output_path_for(cleaned, args.output_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        sections = cleaned["chapter"]["sections"]
        exercises = cleaned["chapter"]["exercises"]["items"]
        manifest.append(
            {
                "id": cleaned["id"],
                "curriculum": cleaned["curriculum"],
                "subject": cleaned["subject"],
                "grade": cleaned["grade"],
                "chapter_number": cleaned["chapter"]["number"],
                "chapter_title": cleaned["chapter"]["title"],
                "section_count": len(sections),
                "subsection_count": sum(len(section["subsections"]) for section in sections),
                "exercise_count": len(exercises),
                "path": str(target),
            }
        )

    manifest_path = args.output_dir / MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "textbook_source_manifest.v1",
                "source_dir": str(args.source_dir),
                "chapter_count": len(manifest),
                "chapters": manifest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Extracted {len(manifest)} content-only chapter files into {args.output_dir}")
    print(f"Wrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
