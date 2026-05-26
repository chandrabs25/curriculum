"""Deterministic section retrieval over curriculum graph artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from .graph import CurriculumGraph


class LearnerConceptStatus(str, Enum):
    COMPETENT = "competent"
    PARTIAL = "partial"
    MISCONCEPTION = "misconception"


@dataclass(frozen=True)
class LearnerConceptState:
    concept_id: str
    status: LearnerConceptStatus | str
    confidence: float = 1.0
    recency_weight: float = 1.0


@dataclass(frozen=True)
class SectionRetrievalResult:
    section_id: str
    chapter_id: str
    title: str
    summary: str
    score: float
    matched_concept_ids: list[str] = field(default_factory=list)
    prerequisite_section_ids: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    subject: str | None = None
    grade: int | None = None


@dataclass
class CurriculumRetriever:
    graph: CurriculumGraph

    def search(
        self,
        query: str,
        subject: str | None = None,
        grade: int | None = None,
        chapter_id: str | None = None,
        learner_state: list[LearnerConceptState] | None = None,
        limit: int = 10,
        include_prerequisites: bool = True,
    ) -> list[SectionRetrievalResult]:
        query_terms = _terms(query)
        if not query_terms:
            return []

        concept_matches = self.graph.concept_ids_for_query(query)
        state_by_concept = {state.concept_id: state for state in learner_state or []}
        scored: dict[str, dict[str, Any]] = {}

        for section_id, summary in self.graph.section_summaries_by_id.items():
            section = self.graph.sections_by_id.get(section_id, {})
            if not self._passes_filters(summary, section, subject=subject, grade=grade, chapter_id=chapter_id):
                continue
            matched_concepts = [
                cid
                for cid in self.graph.concepts_taught_by_section(section_id)
                if cid in concept_matches
            ]
            score, reasons = self._score_summary(summary, query_terms)
            if matched_concepts:
                score += 10.0 * len(matched_concepts)
                reasons.append("concept_match")
            if score <= 0:
                continue
            score += self._learner_adjustment(section_id, matched_concepts, state_by_concept, reasons)
            self._add_or_update(scored, section_id, summary, section, score, matched_concepts, reasons)

        if include_prerequisites:
            self._add_prerequisites(scored, state_by_concept, subject=subject, grade=grade, chapter_id=chapter_id)

        results = [self._result_from_score(row) for row in scored.values()]
        results.sort(key=lambda row: (-row.score, row.subject or "", row.grade or 0, row.chapter_id, row.section_id))
        return results[:limit]

    def _passes_filters(
        self,
        summary: dict[str, Any],
        section: dict[str, Any],
        *,
        subject: str | None,
        grade: int | None,
        chapter_id: str | None,
    ) -> bool:
        if chapter_id and summary.get("chapter_id") != chapter_id:
            return False
        if subject and section.get("subject") != subject:
            return False
        if grade is not None and section.get("grade") != grade:
            return False
        return True

    def _score_summary(self, summary: dict[str, Any], query_terms: list[str]) -> tuple[float, list[str]]:
        title = str(summary.get("title") or "").lower()
        key_terms = " ".join(str(term) for term in summary.get("key_terms") or []).lower()
        summary_text = str(summary.get("summary") or "").lower()
        score = 0.0
        reasons: list[str] = []
        title_tokens = _tokens(title)
        key_tokens = _tokens(key_terms)
        summary_tokens = _tokens(summary_text)
        title_hits = sum(title_tokens.count(term) for term in query_terms)
        key_hits = sum(key_tokens.count(term) for term in query_terms)
        summary_hits = sum(summary_tokens.count(term) for term in query_terms)
        if title_hits:
            score += 4.0 * title_hits
            reasons.append("title_match")
        if key_hits:
            score += 3.0 * key_hits
            reasons.append("key_term_match")
        if summary_hits:
            score += 1.0 * summary_hits
            reasons.append("summary_match")
        return score, reasons

    def _learner_adjustment(
        self,
        section_id: str,
        matched_concepts: list[str],
        state_by_concept: dict[str, LearnerConceptState],
        reasons: list[str],
    ) -> float:
        section_concepts = set(self.graph.concepts_taught_by_section(section_id)) | set(matched_concepts)
        adjustment = 0.0
        for concept_id in section_concepts:
            state = state_by_concept.get(concept_id)
            if not state:
                continue
            weight = max(0.0, min(1.0, state.confidence)) * max(0.0, min(1.0, state.recency_weight))
            status = state.status.value if isinstance(state.status, LearnerConceptStatus) else str(state.status)
            if status == LearnerConceptStatus.MISCONCEPTION.value:
                adjustment += 5.0 * weight
                reasons.append("learner_misconception")
            elif status == LearnerConceptStatus.PARTIAL.value:
                adjustment += 2.5 * weight
                reasons.append("learner_partial")
            elif status == LearnerConceptStatus.COMPETENT.value:
                adjustment -= 3.0 * weight
                reasons.append("learner_competency")
        return adjustment

    def _add_prerequisites(
        self,
        scored: dict[str, dict[str, Any]],
        state_by_concept: dict[str, LearnerConceptState],
        *,
        subject: str | None,
        grade: int | None,
        chapter_id: str | None,
    ) -> None:
        existing_ids = list(scored)
        for section_id in existing_ids:
            base = scored[section_id]
            for prereq_id in self.graph.prerequisite_sections(section_id):
                summary = self.graph.section_summaries_by_id.get(prereq_id)
                if not summary:
                    continue
                section = self.graph.sections_by_id.get(prereq_id, {})
                if not self._passes_filters(summary, section, subject=subject, grade=grade, chapter_id=chapter_id):
                    continue
                prereq_concepts = self.graph.concepts_taught_by_section(prereq_id)
                reasons = ["prerequisite"]
                score = max(0.1, float(base["score"]) * 0.45)
                score += self._learner_adjustment(prereq_id, prereq_concepts, state_by_concept, reasons)
                self._add_or_update(scored, prereq_id, summary, section, score, prereq_concepts, reasons, prerequisite_for=section_id)

    def _add_or_update(
        self,
        scored: dict[str, dict[str, Any]],
        section_id: str,
        summary: dict[str, Any],
        section: dict[str, Any],
        score: float,
        matched_concepts: list[str],
        reasons: list[str],
        *,
        prerequisite_for: str | None = None,
    ) -> None:
        existing = scored.get(section_id)
        if not existing:
            scored[section_id] = {
                "section_id": section_id,
                "chapter_id": summary.get("chapter_id") or section.get("chapter_id") or "",
                "title": summary.get("title") or section.get("title") or "",
                "summary": summary.get("summary") or "",
                "score": round(score, 4),
                "matched_concept_ids": set(matched_concepts),
                "prerequisite_section_ids": set(),
                "reasons": set(reasons),
                "subject": section.get("subject"),
                "grade": section.get("grade"),
            }
            existing = scored[section_id]
        else:
            existing["score"] = round(max(float(existing["score"]), score), 4)
            existing["matched_concept_ids"].update(matched_concepts)
            existing["reasons"].update(reasons)
        if prerequisite_for:
            existing["prerequisite_section_ids"].add(prerequisite_for)

    def _result_from_score(self, row: dict[str, Any]) -> SectionRetrievalResult:
        return SectionRetrievalResult(
            section_id=row["section_id"],
            chapter_id=row["chapter_id"],
            title=row["title"],
            summary=row["summary"],
            score=float(row["score"]),
            matched_concept_ids=sorted(row["matched_concept_ids"]),
            prerequisite_section_ids=sorted(row["prerequisite_section_ids"]),
            reasons=sorted(row["reasons"]),
            subject=row.get("subject"),
            grade=row.get("grade"),
        )


def _terms(query: str) -> list[str]:
    return _tokens(str(query or "").replace("_", " "))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())
