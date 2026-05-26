"""Query helpers over generated curriculum graph artifacts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
import re
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

    @cached_property
    def section_summaries_by_id(self) -> dict[str, dict[str, Any]]:
        return {row["section_id"]: row for row in self.artifacts.section_summaries() if row.get("section_id")}

    @cached_property
    def sections_by_id(self) -> dict[str, dict[str, Any]]:
        return {section["id"]: section for section in self.textbooks.iter_sections() if section.get("id")}

    @cached_property
    def sections_by_chapter_id(self) -> dict[str, list[dict[str, Any]]]:
        by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for section in self.textbooks.iter_sections():
            by_chapter[section["chapter_id"]].append(section)
        return dict(by_chapter)

    @cached_property
    def concepts_by_id(self) -> dict[str, dict[str, Any]]:
        return {row["concept_id"]: row for row in self.artifacts.concepts() if row.get("concept_id")}

    @cached_property
    def relationships(self) -> list[dict[str, Any]]:
        accepted = self.artifacts.relationships(include_review=self.include_review)
        return accepted or self.artifacts.raw_section_relationships()

    @cached_property
    def relationships_by_type_index(self) -> dict[str, list[dict[str, Any]]]:
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.relationships:
            by_type[str(row.get("type") or "")].append(row)
        return dict(by_type)

    @cached_property
    def taught_concepts_by_section(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("TEACHES_CONCEPT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["from_id"]].append(row["to_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    @cached_property
    def teaching_sections_by_concept(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("TEACHES_CONCEPT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["to_id"]].append(row["from_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    @cached_property
    def required_concepts_by_section(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("REQUIRES_CONCEPT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["from_id"]].append(row["to_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    @cached_property
    def prerequisite_sections_by_section(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("DEPENDS_ON_UNIT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["from_id"]].append(row["to_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    @cached_property
    def dependent_sections_by_section(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("DEPENDS_ON_UNIT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["to_id"]].append(row["from_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    def relationships_by_type(self, rel_type: str) -> list[dict[str, Any]]:
        return self.relationships_by_type_index.get(rel_type, [])

    def concepts_taught_by_section(self, section_id: str) -> list[str]:
        return self.taught_concepts_by_section.get(section_id, [])

    def sections_teaching_concept(self, concept_id: str) -> list[str]:
        return self.teaching_sections_by_concept.get(concept_id, [])

    def required_concepts_for_section(self, section_id: str) -> list[str]:
        return self.required_concepts_by_section.get(section_id, [])

    def prerequisite_sections(self, section_id: str) -> list[str]:
        return self.prerequisite_sections_by_section.get(section_id, [])

    def dependents_of_section(self, section_id: str) -> list[str]:
        return self.dependent_sections_by_section.get(section_id, [])

    def concept_ids_for_query(self, query: str) -> list[str]:
        query_text = _normalize_text(query)
        if not query_text:
            return []
        query_tokens = set(_tokens(query_text))
        matches = []
        for concept_id, concept in self.concepts_by_id.items():
            labels = {
                concept_id,
                concept_id.replace("concept:", ""),
                str(concept.get("canonical_label") or ""),
                str(concept.get("normalized_label") or "").replace("_", " "),
                *[str(alias) for alias in concept.get("aliases", [])],
            }
            if any(_concept_label_matches(_normalize_text(label), query_text, query_tokens) for label in labels):
                matches.append(concept_id)
        return _dedupe(matches)

    def teaching_sections_for_concepts(self, concept_ids: list[str]) -> list[str]:
        section_ids: list[str] = []
        for concept_id in concept_ids:
            section_ids.extend(self.sections_teaching_concept(concept_id))
        return _dedupe(section_ids)

    def prerequisite_concepts_for_sections(self, section_ids: list[str]) -> list[str]:
        concept_ids: list[str] = []
        for section_id in section_ids:
            concept_ids.extend(self.required_concepts_for_section(section_id))
        return _dedupe(concept_ids)

    def prerequisite_sections_for_sections(self, section_ids: list[str]) -> list[str]:
        prereq_ids: list[str] = []
        for section_id in section_ids:
            prereq_ids.extend(self.prerequisite_sections(section_id))
        return _dedupe(prereq_ids)

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
            tokens = _tokens(text)
            score = sum(tokens.count(term) for term in terms)
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


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().replace("_", " ").split())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _concept_label_matches(label: str, query_text: str, query_tokens: set[str]) -> bool:
    if not label:
        return False
    label_tokens = set(_tokens(label))
    if len(label_tokens) <= 1:
        return label in query_tokens
    return label in query_text
