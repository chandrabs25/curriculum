"""Repositories over cleaned textbook JSON and generated graph artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


@dataclass(frozen=True)
class TextbookStore:
    root: Path = Path(".")
    manifest_path: Path = Path("data/textbook_sources/manifest.json")

    @property
    def manifest(self) -> dict[str, Any]:
        return read_json(self.root / self.manifest_path)

    def chapter_refs(
        self,
        *,
        subject: str | None = None,
        grade: int | None = None,
        chapter_id: str | None = None,
    ) -> list[dict[str, Any]]:
        refs = []
        for row in self.manifest.get("chapters", []):
            if subject and row.get("subject") != subject:
                continue
            if grade is not None and int(row.get("grade")) != grade:
                continue
            if chapter_id and row.get("id") != chapter_id:
                continue
            refs.append(row)
        return refs

    def load_chapter(self, chapter_id: str) -> dict[str, Any]:
        matches = self.chapter_refs(chapter_id=chapter_id)
        if not matches:
            raise KeyError(f"Unknown chapter_id: {chapter_id}")
        return read_json(self.root / matches[0]["path"])

    def iter_chapters(self, **filters: Any) -> Iterable[dict[str, Any]]:
        for ref in self.chapter_refs(**filters):
            yield read_json(self.root / ref["path"])

    def iter_sections(self, **filters: Any) -> Iterable[dict[str, Any]]:
        for chapter in self.iter_chapters(**filters):
            for section in chapter["chapter"].get("sections", []):
                yield {
                    "chapter_id": chapter["id"],
                    "subject": chapter["subject"],
                    "grade": chapter["grade"],
                    **section,
                }

    def section_ids(self, **filters: Any) -> set[str]:
        return {section["id"] for section in self.iter_sections(**filters)}

    def get_section(self, section_id: str) -> dict[str, Any]:
        for section in self.iter_sections():
            if section["id"] == section_id:
                return section
        raise KeyError(f"Unknown section_id: {section_id}")


@dataclass(frozen=True)
class ArtifactStore:
    root: Path = Path(".")
    artifact_dir: Path = Path("data/relationship_artifacts")

    def path(self, name: str) -> Path:
        return self.root / self.artifact_dir / name

    def section_summaries(self) -> list[dict[str, Any]]:
        return read_jsonl(self.path("section_summaries.jsonl"))

    def concepts(self) -> list[dict[str, Any]]:
        return read_jsonl(self.path("canonical_concepts.jsonl"))

    def relationships(self, *, include_review: bool = False) -> list[dict[str, Any]]:
        rows = read_jsonl(self.path("accepted_relationships.jsonl"))
        if include_review:
            rows.extend(read_jsonl(self.path("review/relationships.jsonl")))
        return rows

    def raw_section_relationships(self) -> list[dict[str, Any]]:
        rows = read_jsonl(self.path("raw_section_concept_relationships.jsonl"))
        rows.extend(read_jsonl(self.path("raw_section_dependency_relationships.jsonl")))
        return rows
