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
        "grounding_section_ids": {"type": "array", "items": {"type": "string"}},
        "options": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "maxLength": 90},
                    "user_facing_description": {"type": "string", "maxLength": 180},
                    "refined_query": {"type": "string", "maxLength": 120},
                    "grounding_section_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "label",
                    "user_facing_description",
                    "refined_query",
                    "grounding_section_ids",
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
        "grounding_section_ids",
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
    concept_ids = graph.concept_ids_for_query(query)[:CONCEPT_CANDIDATE_LIMIT]
    retrieved = retriever.search(
        query,
        subject=subject,
        grade=grade,
        chapter_id=chapter_id,
        limit=limit,
        include_prerequisites=False,
        include_soft_links=False,
    )
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
            for row in retrieved
        ],
        "instructions": {
            "user_facing_options": "Phrase options as what the learner wants to learn, not as section titles.",
            "internal_grounding": "Use section IDs only as internal grounding_section_ids.",
        },
    }
    return IntentClassificationPacket(packet)


def build_intent_classification_prompt(packet: IntentClassificationPacket) -> str:
    schema_example = {
        "needs_user_choice": False,
        "question": "",
        "confirmed_label": "string",
        "confirmed_summary": "string",
        "refined_query": "string",
        "grounding_section_ids": ["string"],
        "options": [
            {
                "label": "string",
                "user_facing_description": "string",
                "refined_query": "string",
                "grounding_section_ids": ["string"],
            }
        ],
    }
    return f"""Classify the learner's intent before curriculum retrieval. The learner is in high interested in studies.

Use the compact title/concept clues to infer what the learner may mean. Do not design a curriculum.

Intent packet:
{packet.to_json()}

Final task:
- Your first character must be {{ and your last character must be }}.
- Do not write analysis, reasoning, markdown, or prose.
- If the query is specific enough, return needs_user_choice=false, fill confirmed_label, confirmed_summary, refined_query, grounding_section_ids, and return options=[].
- If the query can reasonably mean multiple learning goals, return needs_user_choice=true, fill question and 2-3 options. Set confirmed_label="", confirmed_summary="", refined_query="", and grounding_section_ids=[].
- Keep every label under 10 words and every description under 18 words.
- User-facing labels and descriptions must describe learning goals, not textbook section titles.
- Do not copy section titles as option labels.
- Do not invent status values, original_query echoes, or intent IDs. The backend assigns them after parsing.
- Keep grounding_section_ids internal and preserve IDs exactly.
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
    allowed_sections = {row["section_id"] for row in packet_data.get("candidate_sections", [])}
    needs_user_choice = bool(payload.get("needs_user_choice"))
    confirmed = _confirmed_intent_row(payload, allowed_sections)
    options = [
        _option_row(row, allowed_sections, index)
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


def _confirmed_intent_row(value: Any, allowed_sections: set[str]) -> dict[str, Any] | None:
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
        "grounding_section_ids": _valid_section_ids(value.get("grounding_section_ids"), allowed_sections),
    }


def _option_row(value: dict[str, Any], allowed_sections: set[str], index: int) -> dict[str, Any]:
    return {
        "label": _required_str(value, "label"),
        "user_facing_description": _required_str(value, "user_facing_description"),
        "refined_query": _required_str(value, "refined_query"),
        "grounding_section_ids": _valid_section_ids(value.get("grounding_section_ids"), allowed_sections),
    }


def _valid_section_ids(value: Any, allowed_sections: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(row) for row in value if str(row) in allowed_sections]


def _required_str(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"Intent response missing required field {key}")
    return value


def _concept_label(graph: CurriculumGraph, concept_id: str) -> str:
    row = graph.concepts_by_id.get(concept_id) or {}
    return str(row.get("canonical_label") or row.get("normalized_label") or concept_id)
