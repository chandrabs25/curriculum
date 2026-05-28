"""LLM-assisted learner intent classification before retrieval planning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .graph import CurriculumGraph
from .retrieval import CurriculumRetriever


INTENT_CANDIDATE_LIMIT = 12
CONCEPT_CANDIDATE_LIMIT = 12
INTENT_OUTPUT_MAX_TOKENS = 1400
INTENT_SECTION_CLUE_LIMIT = 8
DIRECT_SECTION_CLUE_REASONS = {"title_match", "key_term_match", "summary_match"}


class IntentLLMClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a JSON-compatible intent-classification response."""


INTENT_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "needs_user_choice": {"type": "boolean"},
        "question": {"type": "string"},
        "confirmed_label": {"type": "string", "maxLength": 90},
        "confirmed_summary": {"type": "string", "maxLength": 180},
        "refined_query": {"type": "string", "maxLength": 120},
        "options": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "maxLength": 90},
                    "user_facing_description": {"type": "string", "maxLength": 180},
                    "refined_query": {"type": "string", "maxLength": 120},
                },
                "required": [
                    "label",
                    "user_facing_description",
                    "refined_query",
                ],
            },
        },
    },
    "required": [
        "needs_user_choice",
        "question",
        "confirmed_label",
        "confirmed_summary",
        "refined_query",
        "options",
    ],
}


@dataclass(frozen=True)
class IntentClassificationPacket:
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False)


@dataclass
class IntentClassifier:
    graph: CurriculumGraph
    retriever: CurriculumRetriever
    llm_client: IntentLLMClient

    def classify(
        self,
        query: str,
        *,
        subject: str | None = None,
        grade: int | None = None,
        chapter_id: str | None = None,
        limit: int = INTENT_CANDIDATE_LIMIT,
    ) -> dict[str, Any]:
        packet = build_intent_classification_packet(
            self.graph,
            self.retriever,
            query,
            subject=subject,
            grade=grade,
            chapter_id=chapter_id,
            limit=limit,
        )
        prompt = build_intent_classification_prompt(packet)
        payload = self.llm_client.generate_json(prompt, INTENT_CLASSIFICATION_SCHEMA)
        return intent_classification_from_payload(payload, packet)


def build_intent_classification_packet(
    graph: CurriculumGraph,
    retriever: CurriculumRetriever,
    query: str,
    *,
    subject: str | None = None,
    grade: int | None = None,
    chapter_id: str | None = None,
    limit: int = INTENT_CANDIDATE_LIMIT,
) -> IntentClassificationPacket:
    candidate_sections = _intent_section_clues(
        retriever.search(
            query,
            subject=subject,
            grade=grade,
            chapter_id=chapter_id,
            limit=max(limit * 2, INTENT_SECTION_CLUE_LIMIT),
            include_prerequisites=False,
            include_soft_links=False,
        )
    )
    section_concept_ids = [
        concept_id
        for row in candidate_sections
        for concept_id in row.matched_concept_ids
    ]
    concept_ids = _dedupe(section_concept_ids + graph.concept_ids_for_query(query))[:CONCEPT_CANDIDATE_LIMIT]
    packet = {
        "original_query": query,
        "matched_concepts": [
            {
                "concept_id": concept_id,
                "label": _concept_label(graph, concept_id),
            }
            for concept_id in concept_ids
        ],
        "candidate_sections": [
            {
                "section_id": row.section_id,
                "title": row.title,
                "subject": row.subject,
                "grade": row.grade,
                "chapter_id": row.chapter_id,
                "reasons": row.reasons,
                "matched_concept_ids": row.matched_concept_ids,
            }
            for row in candidate_sections[:INTENT_SECTION_CLUE_LIMIT]
        ],
        "instructions": {
            "corpus_constraint": "Only refine toward learning goals supported by matched_concepts or candidate_sections.",
            "user_facing_options": "Phrase options as what the learner wants to learn, not as section titles.",
        },
    }
    return IntentClassificationPacket(packet)


def _intent_section_clues(rows: list[Any]) -> list[Any]:
    usable = [
        row
        for row in rows
        if set(row.reasons) & (DIRECT_SECTION_CLUE_REASONS | {"concept_match"})
    ]
    usable.sort(key=_intent_section_sort_key)
    return usable


def _intent_section_sort_key(row: Any) -> tuple[int, int, float, str]:
    reasons = set(row.reasons)
    direct_rank = 0 if reasons & DIRECT_SECTION_CLUE_REASONS else 1
    concept_rank = 0 if "concept_match" in reasons else 1
    return (direct_rank, concept_rank, -float(row.score), row.section_id)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def build_intent_classification_prompt(packet: IntentClassificationPacket) -> str:
    schema_example = {
        "needs_user_choice": False,
        "question": "",
        "confirmed_label": "string",
        "confirmed_summary": "string",
        "refined_query": "string",
        "options": [
            {
                "label": "string",
                "user_facing_description": "string",
                "refined_query": "string",
            }
        ],
    }
    return f"""Classify the learner's intent before curriculum retrieval for a textbook-grounded curriculum app.

Use only the provided concept and section-title clues to infer what the learner may mean. Do not design a curriculum.

Intent packet:
{packet.to_json()}

Final task:
- Your first character must be {{ and your last character must be }}.
- Do not write analysis, reasoning, markdown, or prose.
- If the query is specific enough, return needs_user_choice=false, fill confirmed_label, confirmed_summary, refined_query, and return options=[].
- If the query can reasonably mean multiple learning goals, return needs_user_choice=true, fill question and 2-3 options. Set confirmed_label="", confirmed_summary="", and refined_query="".
- Keep every label under 10 words and every description under 18 words.
- User-facing labels and descriptions must describe learning goals, not textbook section titles.
- Do not copy section titles as option labels.
- Option labels should sound like learner goals, for example "Understand gravitational force laws", not "Universal Law of Gravitation".
- Do not propose topics that are not supported by matched_concepts or candidate_sections.
- If candidate evidence is thin, confirm a conservative textbook-level interpretation instead of inventing advanced options.
- Never introduce out-of-corpus directions such as relativity, quantum theory, or modern discoveries unless those ideas appear in the packet.
- Do not invent status values, original_query echoes, or intent IDs. The backend assigns them after parsing.
- Keep refined_query short and useful for the later retrieval call.
- Return compact JSON only.

Required JSON shape:
{json.dumps(schema_example, ensure_ascii=False)}
"""


def intent_classification_from_payload(
    payload: dict[str, Any],
    packet: IntentClassificationPacket,
) -> dict[str, Any]:
    packet_data = packet.to_dict()
    needs_user_choice = bool(payload.get("needs_user_choice"))
    confirmed = _confirmed_intent_row(payload)
    options = [
        _option_row(row, index)
        for index, row in enumerate(payload.get("options") or [], start=1)
        if isinstance(row, dict)
    ]
    if needs_user_choice:
        status = "needs_clarification"
    else:
        status = "confirmed"
    if status == "confirmed" and not confirmed:
        raise ValueError("Confirmed intent response must include confirmed_intent and needs_user_choice=false")
    if status == "needs_clarification" and len(options) < 2:
        raise ValueError("Clarification response must include at least two options and needs_user_choice=true")
    return {
        "status": status,
        "original_query": packet_data["original_query"],
        "needs_user_choice": needs_user_choice,
        "question": str(payload.get("question") or ""),
        "confirmed_intent": confirmed,
        "options": options,
        "classification_packet": packet_data,
    }


def _confirmed_intent_row(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not value:
        return None
    label = str(value.get("confirmed_label") or "").strip()
    summary = str(value.get("confirmed_summary") or "").strip()
    refined_query = str(value.get("refined_query") or "").strip()
    if not label and not summary and not refined_query:
        return None
    return {
        "label": _required_str(value, "confirmed_label"),
        "user_facing_summary": _required_str(value, "confirmed_summary"),
        "refined_query": _required_str(value, "refined_query"),
    }


def _option_row(value: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "label": _required_str(value, "label"),
        "user_facing_description": _required_str(value, "user_facing_description"),
        "refined_query": _required_str(value, "refined_query"),
    }


def _required_str(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"Intent response missing required field {key}")
    return value


def _concept_label(graph: CurriculumGraph, concept_id: str) -> str:
    row = graph.concepts_by_id.get(concept_id) or {}
    return str(row.get("canonical_label") or row.get("normalized_label") or concept_id)
