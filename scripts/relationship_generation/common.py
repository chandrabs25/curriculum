#!/usr/bin/env python3
"""Shared utilities for textbook relationship-generation scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


ARTIFACT_DIR = Path("data/relationship_artifacts")
SOURCE_MANIFEST = Path("data/textbook_sources/manifest.json")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

RELATIONSHIP_TYPES = {
    "DEPENDS_ON_UNIT",
    "REQUIRES_CONCEPT",
    "TEACHES_CONCEPT",
    "TESTS_UNIT",
    "TESTS_CONCEPT",
}


@dataclass(frozen=True)
class ChapterRef:
    id: str
    subject: str
    grade: int
    chapter_number: int | str
    chapter_title: str
    path: Path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return rows


def stable_hash(value: Any, prefix: str) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


def normalize_label(label: str) -> str:
    text = (label or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    for prefix in ("concept_of_", "introduction_to_", "basics_of_", "basic_"):
        if text.startswith(prefix) and len(text) > len(prefix) + 3:
            text = text[len(prefix):]
    return text or "unnamed_concept"


def concept_id_from_label(label: str) -> str:
    return f"concept:{normalize_label(label)}"


def compact_text(text: str, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def load_manifest(
    manifest_path: Path = SOURCE_MANIFEST,
    *,
    subject: str | None = None,
    grade: int | None = None,
    chapter_id: str | None = None,
    limit: int | None = None,
) -> list[ChapterRef]:
    manifest = read_json(manifest_path)
    refs: list[ChapterRef] = []
    for row in manifest.get("chapters", []):
        if subject and row.get("subject") != subject:
            continue
        if grade is not None and int(row.get("grade")) != grade:
            continue
        if chapter_id and row.get("id") != chapter_id:
            continue
        refs.append(
            ChapterRef(
                id=row["id"],
                subject=row["subject"],
                grade=int(row["grade"]),
                chapter_number=row["chapter_number"],
                chapter_title=row["chapter_title"],
                path=Path(row["path"]),
            )
        )
    refs.sort(key=lambda r: (r.subject, r.grade, str(r.chapter_number)))
    return refs[:limit] if limit else refs


def add_common_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, default=SOURCE_MANIFEST)
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--subject", choices=["physics", "chemistry", "biology"])
    parser.add_argument("--grade", type=int, choices=[11, 12])
    parser.add_argument("--chapter-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")


def load_chapter_context(chapter_path: Path, max_chars: int = 45000) -> dict[str, Any]:
    data = read_json(chapter_path)
    chapter = data["chapter"]
    sections: list[dict[str, Any]] = []
    chars = 0

    for section in chapter.get("sections", []):
        section_row = {
            "id": section["id"],
            "number": section.get("number"),
            "title": section.get("title"),
            "content_text": compact_text(section.get("content_text") or "", 800),
            "subsections": [],
        }
        chars += len(json.dumps(section_row, ensure_ascii=False))
        for subsection in section.get("subsections", []):
            row = {
                "id": subsection["id"],
                "order": subsection.get("order"),
                "title": subsection.get("title"),
                "content_type": subsection.get("content_type"),
                "content_text": compact_text(subsection.get("content_text") or "", 1100),
                "worked_examples": subsection.get("worked_examples") or [],
                "diagrams": subsection.get("diagrams") or [],
                "tables": subsection.get("tables") or [],
            }
            chars += len(json.dumps(row, ensure_ascii=False))
            if chars > max_chars:
                row["content_text"] = compact_text(row["content_text"], 240)
            section_row["subsections"].append(row)
        sections.append(section_row)

    exercises = []
    for exercise in chapter.get("exercises", {}).get("items", []):
        row = {
            "id": exercise["id"],
            "number": exercise.get("number"),
            "difficulty": exercise.get("difficulty"),
            "exercise_type": exercise.get("exercise_type"),
            "problem": compact_text(exercise.get("problem") or "", 900),
        }
        exercises.append(row)

    return {
        "id": data["id"],
        "subject": data["subject"],
        "grade": data["grade"],
        "chapter": {
            "id": chapter["id"],
            "number": chapter.get("number"),
            "title": chapter.get("title"),
            "summary": compact_text(chapter.get("summary") or "", 2500),
            "sections": sections,
            "exercises": exercises,
        },
    }


def load_full_chapter(chapter_path: Path) -> dict[str, Any]:
    """Load a cleaned source chapter without prompt compaction."""
    return read_json(chapter_path)


def iter_units(source_chapter: dict[str, Any]) -> list[dict[str, Any]]:
    """Return section and subsection units from a cleaned source chapter."""
    chapter_id = source_chapter["id"]
    units: list[dict[str, Any]] = []
    for section in source_chapter["chapter"].get("sections", []):
        section_unit = {
            "unit_id": section["id"],
            "chapter_id": chapter_id,
            "unit_type": "section",
            "parent_section_id": None,
            "number": section.get("number"),
            "order": section.get("number"),
            "title": section.get("title") or "",
            "content_type": "section",
            "content_text": section.get("content_text") or "",
            "subsection_ids": [s["id"] for s in section.get("subsections", [])],
            "child_subsections": [
                {
                    "id": s["id"],
                    "order": s.get("order"),
                    "title": s.get("title") or "",
                    "content_type": s.get("content_type") or "explanation",
                    "content_text": s.get("content_text") or "",
                }
                for s in section.get("subsections", [])
            ],
            "worked_examples": [],
            "diagrams": [],
            "tables": [],
        }
        units.append(section_unit)
        for subsection in section.get("subsections", []):
            units.append(
                {
                    "unit_id": subsection["id"],
                    "chapter_id": chapter_id,
                    "unit_type": "subsection",
                    "parent_section_id": section["id"],
                    "number": section.get("number"),
                    "order": subsection.get("order"),
                    "title": subsection.get("title") or "",
                    "content_type": subsection.get("content_type") or "explanation",
                    "content_text": subsection.get("content_text") or "",
                    "subsection_ids": [],
                    "worked_examples": subsection.get("worked_examples") or [],
                    "diagrams": subsection.get("diagrams") or [],
                    "tables": subsection.get("tables") or [],
                }
            )
    return units


def iter_exercises(source_chapter: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exercises from a cleaned source chapter."""
    chapter_id = source_chapter["id"]
    rows = []
    for exercise in source_chapter["chapter"].get("exercises", {}).get("items", []):
        rows.append(
            {
                "exercise_id": exercise["id"],
                "chapter_id": chapter_id,
                "number": exercise.get("number"),
                "problem": exercise.get("problem") or "",
                "solution": exercise.get("solution"),
                "difficulty": exercise.get("difficulty"),
                "exercise_type": exercise.get("exercise_type"),
            }
        )
    return rows


def completed_ids(path: Path, key: str) -> set[str]:
    return {row[key] for row in read_jsonl(path) if row.get(key)}


def load_unit_summaries(path: Path) -> dict[str, dict[str, Any]]:
    return {row["unit_id"]: row for row in read_jsonl(path) if row.get("unit_id")}


def chapter_unit_summaries(path: Path, chapter_id: str) -> list[dict[str, Any]]:
    return [row for row in read_jsonl(path) if row.get("chapter_id") == chapter_id]


def relevant_concepts_for_text(
    chapter_id: str,
    subject: str,
    text: str,
    concepts: list[dict[str, Any]],
    limit: int = 120,
) -> list[dict[str, Any]]:
    """Select a compact concept registry subset for a prompt."""
    scored: list[tuple[int, dict[str, Any]]] = []
    haystack = (text or "").lower()
    for concept in concepts:
        score = 0
        if chapter_id in concept.get("source_chapter_ids", []):
            score += 10
        if subject in concept.get("subjects", []):
            score += 3
        labels = [concept.get("canonical_label", ""), concept.get("normalized_label", "").replace("_", " ")]
        labels += concept.get("aliases", [])[:8]
        for label in labels:
            label_text = str(label or "").lower()
            if label_text and label_text in haystack:
                score += 4
        if score > 0:
            scored.append((score, concept))
    scored.sort(key=lambda item: (-item[0], item[1]["concept_id"]))
    return [
        {
            "concept_id": c["concept_id"],
            "canonical_label": c.get("canonical_label", ""),
            "definition": c.get("definition", ""),
            "aliases": c.get("aliases", [])[:8],
        }
        for _, c in scored[:limit]
    ]


def unit_ids_from_chapter(chapter: dict[str, Any]) -> set[str]:
    ids = {chapter["chapter"]["id"]}
    for section in chapter["chapter"].get("sections", []):
        ids.add(section["id"])
        for subsection in section.get("subsections", []):
            ids.add(subsection["id"])
    return ids


def exercise_ids_from_chapter(chapter: dict[str, Any]) -> set[str]:
    return {ex["id"] for ex in chapter["chapter"].get("exercises", [])}


def all_source_ids_from_manifest(manifest_path: Path = SOURCE_MANIFEST) -> tuple[set[str], set[str]]:
    unit_ids: set[str] = set()
    exercise_ids: set[str] = set()
    for ref in load_manifest(manifest_path):
        data = load_chapter_context(ref.path, max_chars=10**9)
        unit_ids.update(unit_ids_from_chapter(data))
        exercise_ids.update(exercise_ids_from_chapter(data))
    return unit_ids, exercise_ids


def completed_chapter_ids(path: Path, key: str = "chapter_id") -> set[str]:
    return {row[key] for row in read_jsonl(path) if row.get(key)}


def validate_confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_label(a), normalize_label(b)).ratio()


def write_error(path: Path, *, stage: str, item_id: str, error: str, payload: Any | None = None) -> None:
    append_jsonl(
        path,
        [
            {
                "stage": stage,
                "item_id": item_id,
                "error": str(error),
                "payload": payload,
            }
        ],
    )


class GeminiClient:
    """Small wrapper around the Google GenAI SDK with JSON parsing fallback."""

    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("Install google-genai to use Gemini scripts: pip install google-genai") from exc
        self._client = genai.Client(api_key=api_key)
        self._types = types
        self.model = model

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        config_kwargs: dict[str, Any] = {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        }
        if schema:
            config_kwargs["response_schema"] = schema
        config = self._types.GenerateContentConfig(**config_kwargs)
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        text = getattr(response, "text", None) or ""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)


def ensure_repo_root() -> None:
    if not Path("data/textbook_sources/manifest.json").exists():
        print("Run this script from the repository root.", file=sys.stderr)
        raise SystemExit(2)
