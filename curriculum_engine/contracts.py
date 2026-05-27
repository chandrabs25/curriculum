"""Stable artifact contracts for generated curriculum graph JSONL files."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ArtifactValidationError(ValueError):
    """Raised when a generated artifact row does not match its contract."""


class RawConceptRelationshipType(str, Enum):
    TEACHES = "teaches"
    REQUIRES = "requires"


class RelationshipType(str, Enum):
    DEPENDS_ON_UNIT = "DEPENDS_ON_UNIT"
    RELATED_BY_CONCEPT = "RELATED_BY_CONCEPT"
    REQUIRES_CONCEPT = "REQUIRES_CONCEPT"
    TEACHES_CONCEPT = "TEACHES_CONCEPT"
    TESTS_UNIT = "TESTS_UNIT"
    TESTS_CONCEPT = "TESTS_CONCEPT"
    TRANSFER_SUPPORTS_UNIT = "TRANSFER_SUPPORTS_UNIT"


def _require_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ArtifactValidationError(f"missing or invalid string field: {key}")
    return value


def _optional_str(row: Mapping[str, Any], key: str, default: str = "") -> str:
    value = row.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ArtifactValidationError(f"invalid string field: {key}")
    return value


def _require_float(row: Mapping[str, Any], key: str) -> float:
    try:
        value = float(row.get(key))
    except (TypeError, ValueError) as exc:
        raise ArtifactValidationError(f"missing or invalid number field: {key}") from exc
    if value < 0.0 or value > 1.0:
        raise ArtifactValidationError(f"confidence out of range: {key}")
    return value


def _str_list(row: Mapping[str, Any], key: str) -> list[str]:
    value = row.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ArtifactValidationError(f"invalid string list field: {key}")
    return value


def _dict_list(row: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = row.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ArtifactValidationError(f"invalid object list field: {key}")
    return value


def _generation(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("generation", {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ArtifactValidationError("invalid generation field")
    return dict(value)


@dataclass(frozen=True)
class SectionSummaryArtifact:
    section_summary_id: str
    chapter_id: str
    section_id: str
    title: str
    summary: str
    key_terms: list[str]
    confidence: float
    section_number: str | None = None
    covered_subsection_ids: list[str] = field(default_factory=list)
    evidence_snippets: list[dict[str, Any]] = field(default_factory=list)
    generation: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "SectionSummaryArtifact":
        return cls(
            section_summary_id=_require_str(row, "section_summary_id"),
            chapter_id=_require_str(row, "chapter_id"),
            section_id=_require_str(row, "section_id"),
            section_number=row.get("section_number") if isinstance(row.get("section_number"), str) else None,
            title=_require_str(row, "title"),
            summary=_require_str(row, "summary"),
            key_terms=_str_list(row, "key_terms"),
            covered_subsection_ids=_str_list(row, "covered_subsection_ids"),
            evidence_snippets=_dict_list(row, "evidence_snippets"),
            confidence=_require_float(row, "confidence"),
            generation=_generation(row),
        )


@dataclass(frozen=True)
class RawConceptArtifact:
    raw_concept_id: str
    chapter_id: str
    source_section_id: str
    relationship_type: RawConceptRelationshipType
    label: str
    normalized_label: str
    candidate_concept_id: str
    confidence: float
    source_unit_ids: list[str]
    evidence: list[dict[str, Any]]
    subject: str = ""
    grade: int | None = None
    chapter_title: str = ""
    definition: str = ""
    reason: str = ""
    generation: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "RawConceptArtifact":
        relationship_value = _require_str(row, "relationship_type")
        try:
            relationship_type = RawConceptRelationshipType(relationship_value)
        except ValueError as exc:
            raise ArtifactValidationError(f"invalid relationship_type: {relationship_value}") from exc
        grade_value = row.get("grade")
        grade = int(grade_value) if grade_value is not None else None
        return cls(
            raw_concept_id=_require_str(row, "raw_concept_id"),
            chapter_id=_require_str(row, "chapter_id"),
            subject=_optional_str(row, "subject"),
            grade=grade,
            chapter_title=_optional_str(row, "chapter_title"),
            source_section_id=_require_str(row, "source_section_id"),
            relationship_type=relationship_type,
            label=_require_str(row, "label"),
            normalized_label=_require_str(row, "normalized_label"),
            candidate_concept_id=_require_str(row, "candidate_concept_id"),
            definition=_optional_str(row, "definition"),
            reason=_optional_str(row, "reason"),
            source_unit_ids=_str_list(row, "source_unit_ids"),
            evidence=_dict_list(row, "evidence"),
            confidence=_require_float(row, "confidence"),
            generation=_generation(row),
        )


@dataclass(frozen=True)
class CanonicalConceptArtifact:
    concept_id: str
    canonical_label: str
    normalized_label: str
    definition: str
    confidence: float
    aliases: list[str] = field(default_factory=list)
    source_raw_concept_ids: list[str] = field(default_factory=list)
    source_chapter_ids: list[str] = field(default_factory=list)
    source_unit_ids: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "CanonicalConceptArtifact":
        return cls(
            concept_id=_require_str(row, "concept_id"),
            canonical_label=_require_str(row, "canonical_label"),
            normalized_label=_require_str(row, "normalized_label"),
            definition=_optional_str(row, "definition"),
            aliases=_str_list(row, "aliases"),
            source_raw_concept_ids=_str_list(row, "source_raw_concept_ids"),
            source_chapter_ids=_str_list(row, "source_chapter_ids"),
            source_unit_ids=_str_list(row, "source_unit_ids"),
            subjects=_str_list(row, "subjects"),
            confidence=_require_float(row, "confidence"),
        )


@dataclass(frozen=True)
class RelationshipArtifact:
    relationship_id: str
    chapter_id: str
    type: RelationshipType
    from_id: str
    to_id: str
    confidence: float
    evidence: dict[str, Any]
    generation: dict[str, Any] = field(default_factory=dict)
    gate_reasons: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    pedagogical_reason: str = ""
    teaching_evidence: str = ""
    source_raw_concept_ids: list[str] = field(default_factory=list)
    source_labels: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "RelationshipArtifact":
        rel_value = _require_str(row, "type")
        try:
            rel_type = RelationshipType(rel_value)
        except ValueError as exc:
            raise ArtifactValidationError(f"invalid relationship type: {rel_value}") from exc
        evidence = row.get("evidence")
        if not isinstance(evidence, dict):
            raise ArtifactValidationError("invalid evidence field")
        if not evidence.get("text") or not evidence.get("reason"):
            raise ArtifactValidationError("relationship evidence requires text and reason")
        return cls(
            relationship_id=_require_str(row, "relationship_id"),
            chapter_id=_require_str(row, "chapter_id"),
            type=rel_type,
            from_id=_require_str(row, "from_id"),
            to_id=_require_str(row, "to_id"),
            confidence=_require_float(row, "confidence"),
            evidence=dict(evidence),
            generation=_generation(row),
            gate_reasons=_str_list(row, "gate_reasons"),
            review_reasons=_str_list(row, "review_reasons"),
            pedagogical_reason=_optional_str(row, "pedagogical_reason"),
            teaching_evidence=_optional_str(row, "teaching_evidence"),
            source_raw_concept_ids=_str_list(row, "source_raw_concept_ids"),
            source_labels=_str_list(row, "source_labels"),
        )


def parse_rows(rows: list[dict[str, Any]], contract: type[Any]) -> list[Any]:
    return [contract.from_row(row) for row in rows]
