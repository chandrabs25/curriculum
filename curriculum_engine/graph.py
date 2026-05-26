"""Query helpers over generated curriculum graph artifacts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import ArtifactStore, TextbookStore


@dataclass
class CurriculumGraph:
    textbooks: TextbookStore
    artifacts: ArtifactStore
    include_review: bool = False

    @classmethod
    def from_repo(cls, root: Path | str = ".") -> "CurriculumGraph":
        root_path = Path(root)
        return cls(textbooks=TextbookStore(root_path), artifacts=ArtifactStore(root_path))

    @property
    def section_summaries_by_id(self) -> dict[str, dict[str, Any]]:
        return {row["section_id"]: row for row in self.artifacts.section_summaries() if row.get("section_id")}

    @property
    def concepts_by_id(self) -> dict[str, dict[str, Any]]:
        return {row["concept_id"]: row for row in self.artifacts.concepts() if row.get("concept_id")}

    @property
    def relationships(self) -> list[dict[str, Any]]:
        accepted = self.artifacts.relationships(include_review=self.include_review)
        return accepted or self.artifacts.raw_section_relationships()

    def relationships_by_type(self, rel_type: str) -> list[dict[str, Any]]:
        return [row for row in self.relationships if row.get("type") == rel_type]

    def concepts_taught_by_section(self, section_id: str) -> list[str]:
        return [
            row["to_id"]
            for row in self.relationships_by_type("TEACHES_CONCEPT")
            if row.get("from_id") == section_id and row.get("to_id")
        ]

    def sections_teaching_concept(self, concept_id: str) -> list[str]:
        return [
            row["from_id"]
            for row in self.relationships_by_type("TEACHES_CONCEPT")
            if row.get("to_id") == concept_id and row.get("from_id")
        ]

    def required_concepts_for_section(self, section_id: str) -> list[str]:
        return [
            row["to_id"]
            for row in self.relationships_by_type("REQUIRES_CONCEPT")
            if row.get("from_id") == section_id and row.get("to_id")
        ]

    def prerequisite_sections(self, section_id: str) -> list[str]:
        return [
            row["to_id"]
            for row in self.relationships_by_type("DEPENDS_ON_UNIT")
            if row.get("from_id") == section_id and row.get("to_id")
        ]

    def dependents_of_section(self, section_id: str) -> list[str]:
        return [
            row["from_id"]
            for row in self.relationships_by_type("DEPENDS_ON_UNIT")
            if row.get("to_id") == section_id and row.get("from_id")
        ]

    def weak_area_remediation_sections(self, concept_ids: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for concept_id in concept_ids:
            for section_id in self.sections_teaching_concept(concept_id):
                if section_id not in seen:
                    seen.add(section_id)
                    ordered.append(section_id)
                for prereq_id in self.prerequisite_sections(section_id):
                    if prereq_id not in seen:
                        seen.add(prereq_id)
                        ordered.append(prereq_id)
        return ordered

    def search_sections(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return []
        scored: list[tuple[int, dict[str, Any]]] = []
        for section_id, summary in self.section_summaries_by_id.items():
            text = " ".join(
                [
                    section_id,
                    str(summary.get("title") or ""),
                    str(summary.get("summary") or ""),
                    " ".join(summary.get("key_terms") or []),
                ]
            ).lower()
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append((score, summary))
        scored.sort(key=lambda item: (-item[0], item[1].get("section_id", "")))
        return [row for _, row in scored[:limit]]

    def chapter_coverage(self) -> dict[str, dict[str, int]]:
        coverage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # type: ignore[assignment]
        for rel in self.relationships:
            chapter_id = rel.get("chapter_id") or "unknown"
            rel_type = rel.get("type") or "unknown"
            coverage[chapter_id][rel_type] += 1
        return {chapter_id: dict(counts) for chapter_id, counts in coverage.items()}
