"""Section-level learning insight reconciliation for checkpoint results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol


class SectionInsightLLMClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return JSON for reconciled section insights."""


SECTION_INSIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "section_insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "understanding_summary": {"type": "string"},
                    "current_status": {"type": "string"},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "misconceptions_or_gaps": {"type": "array", "items": {"type": "string"}},
                    "recommended_adjustment": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence_question_ids": {"type": "array", "items": {"type": "string"}},
                    "supersedes_insight_id": {"type": "string"},
                    "reconciliation_reason": {"type": "string"},
                },
                "required": [
                    "section_id",
                    "understanding_summary",
                    "current_status",
                    "strengths",
                    "misconceptions_or_gaps",
                    "recommended_adjustment",
                    "confidence",
                    "evidence_question_ids",
                    "supersedes_insight_id",
                    "reconciliation_reason",
                ],
            },
        }
    },
    "required": ["section_insights"],
}

VALID_SECTION_STATUSES = {"competent", "partial_understanding", "misconception", "uncertain"}


def generate_section_insights(
    llm_client: SectionInsightLLMClient,
    *,
    learner_id: str,
    curriculum_plan_id: str,
    module_id: str,
    question_results: list[dict[str, Any]],
    checkpoint_mcqs: list[dict[str, Any]],
    existing_section_insights: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    evidence_by_section = _evidence_by_section(question_results, checkpoint_mcqs)
    if not evidence_by_section:
        return []

    existing_by_section = _latest_by_section(existing_section_insights or [], set(evidence_by_section))
    prompt = build_section_insight_prompt(
        learner_id=learner_id,
        curriculum_plan_id=curriculum_plan_id,
        module_id=module_id,
        evidence_by_section=evidence_by_section,
        existing_by_section=existing_by_section,
    )
    payload = llm_client.generate_json(prompt, SECTION_INSIGHT_SCHEMA)
    return section_insights_from_payload(
        payload,
        learner_id=learner_id,
        curriculum_plan_id=curriculum_plan_id,
        module_id=module_id,
        evidence_by_section=evidence_by_section,
        existing_by_section=existing_by_section,
    )


def build_section_insight_prompt(
    *,
    learner_id: str,
    curriculum_plan_id: str,
    module_id: str,
    evidence_by_section: dict[str, list[dict[str, Any]]],
    existing_by_section: dict[str, dict[str, Any]],
) -> str:
    packet = {
        "learner_id": learner_id,
        "curriculum_plan_id": curriculum_plan_id,
        "module_id": module_id,
        "section_evidence": evidence_by_section,
        "existing_section_insights": existing_by_section,
    }
    schema_example = {
        "section_insights": [
            {
                "section_id": "string",
                "understanding_summary": "string",
                "current_status": "competent|partial_understanding|misconception|uncertain",
                "strengths": ["string"],
                "misconceptions_or_gaps": ["string"],
                "recommended_adjustment": "string",
                "confidence": 0.0,
                "evidence_question_ids": ["string"],
                "supersedes_insight_id": "string",
                "reconciliation_reason": "string",
            }
        ]
    }
    return f"""You reconcile checkpoint evidence into current section-level learner insights.

The deterministic grader has already scored each answer. Use the evidence to describe the learner's current understanding for each tested source section. If an existing insight is present for a section, judge whether the new evidence confirms it, improves it, contradicts it, or supersedes it.

Insight evidence packet:
{json.dumps(packet, ensure_ascii=False)}

Now return the current best insight for each section.

Critical rules:
- Return JSON only.
- Produce exactly one insight per section_id in section_evidence.
- Use only section IDs and question IDs from the packet.
- Do not append vague history. Return the current best understanding state.
- current_status must be one of: competent, partial_understanding, misconception, uncertain.
- If an existing insight is replaced or contradicted, set supersedes_insight_id to that prior insight_id; otherwise use an empty string.
- Keep understanding_summary and recommended_adjustment short and actionable.

Required JSON shape:
{json.dumps(schema_example, ensure_ascii=False)}
"""


def section_insights_from_payload(
    payload: dict[str, Any],
    *,
    learner_id: str,
    curriculum_plan_id: str,
    module_id: str,
    evidence_by_section: dict[str, list[dict[str, Any]]],
    existing_by_section: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    rows = payload.get("section_insights")
    if not isinstance(rows, list):
        raise ValueError("Section insight response must include section_insights")
    insights: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        section_id = str(row.get("section_id") or "")
        if section_id not in evidence_by_section or section_id in seen:
            continue
        seen.add(section_id)
        existing = existing_by_section.get(section_id) or {}
        evidence_question_ids = _valid_question_ids(row.get("evidence_question_ids"), evidence_by_section[section_id])
        supersedes = row.get("supersedes_insight_id")
        if supersedes is not None:
            supersedes = str(supersedes).strip() or None
        if not supersedes and existing:
            supersedes = str(existing.get("insight_id") or "").strip() or None
        insight = {
            "insight_id": _stable_insight_id(learner_id, section_id, module_id, evidence_question_ids, now),
            "learner_id": learner_id,
            "curriculum_plan_id": curriculum_plan_id,
            "module_id": module_id,
            "section_id": section_id,
            "understanding_summary": _compact(row.get("understanding_summary"), 420),
            "current_status": _status(row.get("current_status")),
            "strengths": _str_list(row.get("strengths"), limit=5),
            "misconceptions_or_gaps": _str_list(row.get("misconceptions_or_gaps"), limit=5),
            "recommended_adjustment": _compact(row.get("recommended_adjustment"), 360),
            "confidence": _confidence(row.get("confidence")),
            "evidence_question_ids": evidence_question_ids,
            "supersedes_insight_id": supersedes,
            "reconciliation_reason": _compact(row.get("reconciliation_reason"), 360),
            "created_at": now,
        }
        insights.append(insight)
    return insights


def _evidence_by_section(
    question_results: list[dict[str, Any]],
    checkpoint_mcqs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    mcq_by_id = {str(mcq.get("question_id") or ""): mcq for mcq in checkpoint_mcqs}
    evidence: dict[str, list[dict[str, Any]]] = {}
    for result in question_results:
        question_id = str(result.get("question_id") or "")
        mcq = mcq_by_id.get(question_id, {})
        source_section_ids = [str(item) for item in result.get("source_section_ids") or []]
        for section_id in source_section_ids:
            evidence.setdefault(section_id, []).append(
                {
                    "question_id": question_id,
                    "question": mcq.get("question") or "",
                    "selected_option": result.get("selected_option") or "",
                    "correct_option": result.get("correct_option") or "",
                    "is_correct": bool(result.get("is_correct")),
                    "explanation": mcq.get("explanation") or "",
                    "tested_concept_ids": result.get("tested_concept_ids") or [],
                    "diagnostic_purpose": result.get("diagnostic_purpose") or "",
                    "misconception_tags": result.get("misconception_tags") or [],
                }
            )
    return evidence


def _latest_by_section(rows: list[dict[str, Any]], allowed_section_ids: set[str]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        section_id = str(row.get("section_id") or "")
        if section_id not in allowed_section_ids:
            continue
        current = latest.get(section_id)
        if current is None or _created_at_key(row) >= _created_at_key(current):
            latest[section_id] = row
    return latest


def _created_at_key(row: dict[str, Any]) -> str:
    return str(row.get("created_at") or "")


def _valid_question_ids(value: Any, evidence_rows: list[dict[str, Any]]) -> list[str]:
    valid = {str(row.get("question_id")) for row in evidence_rows if row.get("question_id")}
    ids = [item for item in _str_list(value) if item in valid]
    return ids or sorted(valid)


def _stable_insight_id(
    learner_id: str,
    section_id: str,
    module_id: str,
    question_ids: list[str],
    created_at: str,
) -> str:
    raw = json.dumps(
        {
            "learner_id": learner_id,
            "section_id": section_id,
            "module_id": module_id,
            "question_ids": question_ids,
            "created_at": created_at,
        },
        sort_keys=True,
    )
    return "section_insight:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _status(value: Any) -> str:
    status = str(value or "uncertain").strip().lower()
    return status if status in VALID_SECTION_STATUSES else "uncertain"


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _str_list(value: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    rows = [str(item).strip() for item in value if str(item).strip()]
    return rows[:limit] if limit is not None else rows
