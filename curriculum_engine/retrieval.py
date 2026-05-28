"""Deterministic section retrieval over curriculum graph artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from .graph import CurriculumGraph
from .vector_index import SectionVectorIndex


DIRECT_MATCH_REASONS = {
    "vector_match",
    "concept_match",
    "title_match",
    "key_term_match",
    "summary_match",
    "learner_misconception",
    "learner_partial",
    "learner_competency",
    "intent_grounding",
}
ALWAYS_KEEP_DIRECT_REASONS = {"vector_match", "concept_match", "title_match", "intent_grounding"}
META_SECTION_TITLES = {
    "summary",
    "points to ponder",
    "exercises",
    "exercise",
    "answers",
    "answer",
    "appendix",
    "glossary",
    "references",
    "bibliography",
}
MIN_SUMMARY_ONLY_SCORE = 6.0
QUERY_STOPWORDS = {
    "i",
    "me",
    "my",
    "we",
    "want",
    "wants",
    "need",
    "needs",
    "learn",
    "learning",
    "study",
    "studying",
    "understand",
    "to",
    "the",
    "a",
    "an",
    "about",
    "of",
    "on",
    "in",
}


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
    vector_index: SectionVectorIndex | None = None

    def search(
        self,
        query: str,
        subject: str | None = None,
        grade: int | None = None,
        chapter_id: str | None = None,
        learner_state: list[LearnerConceptState] | None = None,
        limit: int = 10,
        include_prerequisites: bool = True,
        include_soft_links: bool = True,
    ) -> list[SectionRetrievalResult]:
        query_terms = _terms(query)
        if not query_terms and not str(query or "").strip():
            return []

        concept_matches = self.graph.concept_ids_for_query(query)
        state_by_concept = {state.concept_id: state for state in learner_state or []}
        scored: dict[str, dict[str, Any]] = {}

        self._add_vector_matches(
            scored,
            query,
            concept_matches,
            state_by_concept,
            subject=subject,
            grade=grade,
            chapter_id=chapter_id,
            limit=max(limit * 4, 20),
        )

        if query_terms:
            for section_id, summary in self.graph.section_summaries_by_id.items():
                section = self.graph.sections_by_id.get(section_id, {})
                if not self._passes_filters(summary, section, subject=subject, grade=grade, chapter_id=chapter_id):
                    continue
                if not self._is_top_level_section(section_id):
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

        self._prune_weak_direct_matches(scored)

        for section_id in self.graph.teaching_sections_for_concepts(concept_matches):
            summary = self.graph.section_summaries_by_id.get(section_id)
            if not summary:
                continue
            section = self.graph.sections_by_id.get(section_id, {})
            if not self._passes_filters(summary, section, subject=subject, grade=grade, chapter_id=chapter_id):
                continue
            matched_concepts = [cid for cid in self.graph.concepts_taught_by_section(section_id) if cid in concept_matches]
            score = 10.0 * max(1, len(matched_concepts))
            reasons = ["concept_match"]
            score += self._learner_adjustment(section_id, matched_concepts, state_by_concept, reasons)
            self._add_or_update(scored, section_id, summary, section, score, matched_concepts, reasons)

        if include_prerequisites:
            self._add_prerequisites(scored, state_by_concept, subject=subject, grade=grade, chapter_id=chapter_id)
        if include_soft_links:
            self._add_soft_links(scored, state_by_concept, subject=subject, grade=grade, chapter_id=chapter_id)

        results = [self._result_from_score(row) for row in scored.values()]
        results.sort(key=lambda row: (-row.score, row.subject or "", row.grade or 0, row.chapter_id, row.section_id))
        return results[:limit]

    def results_for_section_ids(self, section_ids: list[str], *, reason: str = "intent_grounding") -> list[SectionRetrievalResult]:
        results = []
        seen: set[str] = set()
        for section_id in section_ids:
            if section_id in seen:
                continue
            seen.add(section_id)
            summary = self.graph.section_summaries_by_id.get(section_id)
            section = self.graph.sections_by_id.get(section_id, {})
            if not summary or self._is_meta_section(summary, section):
                continue
            chapter_ref = self._chapter_ref(summary.get("chapter_id"))
            matched_concepts = self.graph.concepts_taught_by_section(section_id)
            results.append(
                SectionRetrievalResult(
                    section_id=section_id,
                    chapter_id=str(summary.get("chapter_id") or section.get("chapter_id") or ""),
                    title=str(summary.get("title") or section.get("title") or section_id),
                    summary=str(summary.get("summary") or ""),
                    score=100.0,
                    matched_concept_ids=matched_concepts,
                    prerequisite_section_ids=[],
                    reasons=[reason],
                    subject=section.get("subject") or chapter_ref.get("subject"),
                    grade=int(section.get("grade") or chapter_ref.get("grade") or 0) or None,
                )
            )
        return results

    def _add_vector_matches(
        self,
        scored: dict[str, dict[str, Any]],
        query: str,
        concept_matches: list[str],
        state_by_concept: dict[str, LearnerConceptState],
        *,
        subject: str | None,
        grade: int | None,
        chapter_id: str | None,
        limit: int,
    ) -> None:
        if not self.vector_index:
            return
        for match in self.vector_index.search(query, limit=limit):
            summary = self.graph.section_summaries_by_id.get(match.section_id)
            if not summary:
                continue
            section = self.graph.sections_by_id.get(match.section_id, {})
            if not self._passes_filters(summary, section, subject=subject, grade=grade, chapter_id=chapter_id):
                continue
            section_concepts = self.graph.concepts_taught_by_section(match.section_id)
            matched_concepts = [cid for cid in section_concepts if cid in concept_matches]
            reasons = ["vector_match"]
            if matched_concepts:
                reasons.append("concept_match")
            score = 20.0 * max(0.0, match.score)
            score += 6.0 * len(matched_concepts)
            score += self._learner_adjustment(match.section_id, matched_concepts, state_by_concept, reasons)
            self._add_or_update(scored, match.section_id, summary, section, score, matched_concepts, reasons)

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
        chapter_ref = self._chapter_ref(summary.get("chapter_id"))
        section_subject = section.get("subject") or chapter_ref.get("subject")
        section_grade = section.get("grade") or chapter_ref.get("grade")
        if subject and section_subject != subject:
            return False
        if grade is not None and int(section_grade or -1) != grade:
            return False
        if self._is_meta_section(summary, section):
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
                if not self._is_top_level_section(prereq_id):
                    continue
                prereq_concepts = self.graph.concepts_taught_by_section(prereq_id)
                reasons = ["prerequisite"]
                score = max(0.1, float(base["score"]) * 0.45)
                score += self._learner_adjustment(prereq_id, prereq_concepts, state_by_concept, reasons)
                self._add_or_update(scored, prereq_id, summary, section, score, prereq_concepts, reasons, prerequisite_for=section_id)

    def _add_soft_links(
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
            candidates: list[tuple[str, str, float]] = []
            candidates.extend((sid, "transfer_support", 0.25) for sid in self.graph.transfer_source_sections(section_id)[:2])
            candidates.extend((sid, "related_concept", 0.18) for sid in self.graph.related_sections_by_concept(section_id)[:2])
            for linked_id, reason, weight in candidates:
                summary = self.graph.section_summaries_by_id.get(linked_id)
                if not summary:
                    continue
                section = self.graph.sections_by_id.get(linked_id, {})
                if not self._passes_filters(summary, section, subject=subject, grade=grade, chapter_id=chapter_id):
                    continue
                if not self._is_top_level_section(linked_id):
                    continue
                concepts = self.graph.concepts_taught_by_section(linked_id)
                reasons = [reason]
                score = max(0.1, float(base["score"]) * weight)
                score += self._learner_adjustment(linked_id, concepts, state_by_concept, reasons)
                self._add_or_update(scored, linked_id, summary, section, score, concepts, reasons)

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

    def _chapter_ref(self, chapter_id: Any) -> dict[str, Any]:
        if not chapter_id:
            return {}
        for ref in self.graph.textbooks.chapter_refs(chapter_id=str(chapter_id)):
            return ref
        return {}

    def _is_top_level_section(self, section_id: str) -> bool:
        return section_id in self.graph.sections_by_id

    def _is_meta_section(self, summary: dict[str, Any], section: dict[str, Any]) -> bool:
        title = _normalize_label(summary.get("title") or section.get("title") or "")
        tail = _normalize_label(str(summary.get("section_id") or section.get("id") or "").rsplit(":", 1)[-1])
        return title in META_SECTION_TITLES or tail in META_SECTION_TITLES or any(label in title for label in META_SECTION_TITLES)

    def _prune_weak_direct_matches(self, scored: dict[str, dict[str, Any]]) -> None:
        direct_scores = [
            float(row.get("score") or 0.0)
            for row in scored.values()
            if set(row.get("reasons") or set()) & DIRECT_MATCH_REASONS
        ]
        relative_cutoff = max(0.1, max(direct_scores, default=0.0) * 0.4)
        for section_id, row in list(scored.items()):
            reasons = set(row.get("reasons") or set())
            if not reasons & DIRECT_MATCH_REASONS:
                continue
            if reasons & ALWAYS_KEEP_DIRECT_REASONS:
                continue
            if float(row.get("score") or 0.0) >= relative_cutoff:
                continue
            del scored[section_id]


def _terms(query: str) -> list[str]:
    return [term for term in _tokens(str(query or "").replace("_", " ")) if term not in QUERY_STOPWORDS]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _normalize_label(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").lower().split())
