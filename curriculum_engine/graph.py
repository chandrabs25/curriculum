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
    usable_only: bool = False

    @classmethod
    def from_repo(cls, root: Path | str = ".", *, usable_only: bool = False) -> "CurriculumGraph":
        root_path = Path(root)
        return cls(textbooks=TextbookStore(root_path), artifacts=ArtifactStore(root_path), usable_only=usable_only)

    @cached_property
    def usable_chapter_ids(self) -> set[str]:
        return self.artifacts.usable_chapter_ids() if self.usable_only else set()

    @cached_property
    def section_summaries_by_id(self) -> dict[str, dict[str, Any]]:
        rows = (
            self.artifacts.section_summaries_for_usable_chapters()
            if self.usable_only
            else self.artifacts.section_summaries()
        )
        return {row["section_id"]: row for row in rows if row.get("section_id")}

    @cached_property
    def sections_by_id(self) -> dict[str, dict[str, Any]]:
        return {
            section["id"]: section
            for section in self.textbooks.iter_sections()
            if section.get("id") and self._chapter_allowed(section.get("chapter_id"))
        }

    @cached_property
    def sections_by_chapter_id(self) -> dict[str, list[dict[str, Any]]]:
        by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for section in self.textbooks.iter_sections():
            if not self._chapter_allowed(section.get("chapter_id")):
                continue
            by_chapter[section["chapter_id"]].append(section)
        return dict(by_chapter)

    @cached_property
    def concepts_by_id(self) -> dict[str, dict[str, Any]]:
        return {row["concept_id"]: row for row in self.artifacts.concepts() if row.get("concept_id")}

    @cached_property
    def relationships(self) -> list[dict[str, Any]]:
        accepted = self.artifacts.relationships(include_review=self.include_review)
        rows = accepted or self.artifacts.raw_section_relationships()
        if not self.usable_only:
            return rows
        return [row for row in rows if self._chapter_allowed(row.get("chapter_id"))]

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

    @cached_property
    def transfer_support_sections_by_section(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("TRANSFER_SUPPORTS_UNIT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["from_id"]].append(row["to_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    @cached_property
    def related_sections_by_section_index(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("RELATED_BY_CONCEPT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["from_id"]].append(row["to_id"])
                index[row["to_id"]].append(row["from_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    def relationships_by_type(self, rel_type: str) -> list[dict[str, Any]]:
        return self.relationships_by_type_index.get(rel_type, [])

    def concepts_taught_by_section(self, section_id: str) -> list[str]:
        return self.taught_concepts_by_section.get(section_id, [])

    def teaches_concept_details(self, section_id: str) -> list[dict[str, Any]]:
        return [
            self._concept_relationship_detail(row, "teaching_evidence")
            for row in self.relationships_by_type("TEACHES_CONCEPT")
            if row.get("from_id") == section_id
        ]

    def sections_teaching_concept(self, concept_id: str) -> list[str]:
        return self.teaching_sections_by_concept.get(concept_id, [])

    def required_concepts_for_section(self, section_id: str) -> list[str]:
        return self.required_concepts_by_section.get(section_id, [])

    def requires_concept_details(self, section_id: str) -> list[dict[str, Any]]:
        return [
            self._concept_relationship_detail(row, "pedagogical_reason")
            for row in self.relationships_by_type("REQUIRES_CONCEPT")
            if row.get("from_id") == section_id
        ]

    def prerequisite_sections(self, section_id: str) -> list[str]:
        return self.prerequisite_sections_by_section.get(section_id, [])

    def hard_dependency_edges_for_section(self, section_id: str) -> list[dict[str, Any]]:
        return [
            self._section_link_detail(row, "to_section should be studied before from_section")
            for row in self.relationships_by_type("DEPENDS_ON_UNIT")
            if row.get("from_id") == section_id
        ]

    def dependents_of_section(self, section_id: str) -> list[str]:
        return self.dependent_sections_by_section.get(section_id, [])

    def dependent_edges_for_section(self, section_id: str) -> list[dict[str, Any]]:
        return [
            self._section_link_detail(row, "from_section can be suggested after completing to_section")
            for row in self.relationships_by_type("DEPENDS_ON_UNIT")
            if row.get("to_id") == section_id
        ]

    def transfer_support_sections(self, section_id: str) -> list[str]:
        return self.transfer_support_sections_by_section.get(section_id, [])

    @cached_property
    def transfer_source_sections_by_section(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for row in self.relationships_by_type("TRANSFER_SUPPORTS_UNIT"):
            if row.get("from_id") and row.get("to_id"):
                index[row["to_id"]].append(row["from_id"])
        return {key: _dedupe(values) for key, values in index.items()}

    def transfer_source_sections(self, section_id: str) -> list[str]:
        return self.transfer_source_sections_by_section.get(section_id, [])

    def related_sections_by_concept(self, section_id: str) -> list[str]:
        return self.related_sections_by_section_index.get(section_id, [])

    def optional_support_edges_for_section(self, section_id: str) -> list[dict[str, Any]]:
        edges = [
            self._section_link_detail(row, "to_section can support from_section as an optional transfer bridge")
            for row in self.relationships_by_type("TRANSFER_SUPPORTS_UNIT")
            if row.get("from_id") == section_id
        ]
        edges.extend(
            self._section_link_detail(row, "sections overlap by concept and can be used for reinforcement")
            for row in self.relationships_by_type("RELATED_BY_CONCEPT")
            if row.get("from_id") == section_id or row.get("to_id") == section_id
        )
        return edges

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

    def _chapter_allowed(self, chapter_id: str | None) -> bool:
        return not self.usable_only or bool(chapter_id and chapter_id in self.usable_chapter_ids)

    def _concept_relationship_detail(self, row: dict[str, Any], planning_text_key: str) -> dict[str, Any]:
        concept_id = str(row.get("to_id") or "")
        concept = self.concepts_by_id.get(concept_id, {})
        evidence = row.get("evidence") or {}
        planning_text = str(row.get(planning_text_key) or evidence.get("text") or "")
        return {
            "relationship_id": row.get("relationship_id"),
            "concept_id": concept_id,
            "label": concept.get("canonical_label") or concept.get("normalized_label") or concept_id,
            "confidence": row.get("confidence"),
            planning_text_key: planning_text,
            "evidence_text": evidence.get("text") or "",
            "source_labels": row.get("source_labels") or [],
        }

    def _section_link_detail(self, row: dict[str, Any], planning_meaning: str) -> dict[str, Any]:
        evidence = row.get("evidence") or {}
        return {
            "relationship_id": row.get("relationship_id"),
            "type": row.get("type"),
            "from_section_id": row.get("from_id"),
            "to_section_id": row.get("to_id"),
            "bridge_concept_id": row.get("source_concept_id"),
            "confidence": row.get("confidence"),
            "evidence_text": evidence.get("text") or "",
            "evidence_reason": evidence.get("reason") or "",
            "planning_meaning": planning_meaning,
        }


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
