"""Population-level misunderstanding hotspot detection from checkpoint evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


HOTSPOT_STATUSES = {"candidate", "active", "rejected", "resolved", "superseded"}


class HotspotLLMClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return JSON for aggregate hotspot wording."""


HOTSPOT_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnostic_summary": {"type": "string"},
        "proposed_guidance": {"type": "string"},
        "suggested_activity_adjustment": {"type": "string"},
        "suggested_checkpoint_focus": {"type": "string"},
    },
    "required": [
        "diagnostic_summary",
        "proposed_guidance",
        "suggested_activity_adjustment",
        "suggested_checkpoint_focus",
    ],
}


@dataclass(frozen=True)
class HotspotThresholds:
    min_attempts: int = 8
    min_unique_learners: int = 4
    min_distinct_questions: int = 2
    min_misconception_rate: float = 0.35


def detect_hotspot_candidates(
    evidence_rows: list[dict[str, Any]],
    *,
    active_hotspots: list[dict[str, Any]] | None = None,
    thresholds: HotspotThresholds = HotspotThresholds(),
    llm_client: HotspotLLMClient | None = None,
    now: str | None = None,
) -> list[dict[str, Any]]:
    """Return aggregate candidate hotspots without exposing learner IDs."""
    active_by_key = {
        _key(row.get("section_id"), row.get("concept_id"), row.get("misconception_tag")): row
        for row in active_hotspots or []
        if str(row.get("status") or "") == "active"
    }
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for evidence in evidence_rows:
        created_at = str(evidence.get("created_at") or "")
        source_section_ids = _str_list(evidence.get("source_section_ids"))
        tested_concept_ids = _str_list(evidence.get("tested_concept_ids"))
        misconception_tags = _str_list(evidence.get("misconception_tags"))
        if not source_section_ids or not tested_concept_ids or not misconception_tags:
            continue
        for section_id in source_section_ids:
            for concept_id in tested_concept_ids:
                for tag in misconception_tags:
                    key = _key(section_id, concept_id, tag)
                    active = active_by_key.get(key)
                    window_start = str(
                        (active or {}).get("activated_at")
                        or (active or {}).get("updated_at")
                        or (active or {}).get("created_at")
                        or ""
                    )
                    if window_start and created_at and created_at <= window_start:
                        continue
                    group = grouped.setdefault(
                        key,
                        {
                            "section_id": section_id,
                            "concept_id": concept_id,
                            "misconception_tag": tag,
                            "evidence_window_start": window_start,
                            "attempt_count": 0,
                            "wrong_count": 0,
                            "learners": set(),
                            "questions": set(),
                            "module_design_ids": set(),
                            "diagnostic_purposes": [],
                        },
                    )
                    group["attempt_count"] += 1
                    if not bool(evidence.get("is_correct")):
                        group["wrong_count"] += 1
                    learner_id = str(evidence.get("learner_id") or "")
                    question_id = str(evidence.get("question_id") or "")
                    module_design_id = str(evidence.get("module_design_id") or "")
                    if learner_id:
                        group["learners"].add(learner_id)
                    if question_id:
                        group["questions"].add(question_id)
                    if module_design_id:
                        group["module_design_ids"].add(module_design_id)
                    diagnostic = str(evidence.get("diagnostic_purpose") or "").strip()
                    if diagnostic:
                        group["diagnostic_purposes"].append(diagnostic)

    rows = []
    timestamp = now or datetime.now(timezone.utc).isoformat()
    for group in grouped.values():
        attempt_count = int(group["attempt_count"])
        wrong_count = int(group["wrong_count"])
        unique_learner_count = len(group["learners"])
        distinct_question_count = len(group["questions"])
        misconception_rate = wrong_count / attempt_count if attempt_count else 0.0
        if (
            attempt_count < thresholds.min_attempts
            or unique_learner_count < thresholds.min_unique_learners
            or distinct_question_count < thresholds.min_distinct_questions
            or misconception_rate < thresholds.min_misconception_rate
        ):
            continue
        summary = _summarize_group(group, misconception_rate, llm_client)
        rows.append(
            {
                "hotspot_id": _hotspot_id(group, group["evidence_window_start"]),
                "section_id": group["section_id"],
                "concept_id": group["concept_id"],
                "misconception_tag": group["misconception_tag"],
                "evidence_window_start": group["evidence_window_start"],
                "evidence_window_end": timestamp,
                "module_design_ids": sorted(group["module_design_ids"]),
                "attempt_count": attempt_count,
                "wrong_count": wrong_count,
                "unique_learner_count": unique_learner_count,
                "distinct_question_count": distinct_question_count,
                "misconception_rate": misconception_rate,
                "diagnostic_summary": summary["diagnostic_summary"],
                "proposed_guidance": summary["proposed_guidance"],
                "reviewed_guidance": "",
                "suggested_activity_adjustment": summary["suggested_activity_adjustment"],
                "suggested_checkpoint_focus": summary["suggested_checkpoint_focus"],
                "status": "candidate",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
    return rows


def build_hotspot_summary_prompt(group: dict[str, Any], misconception_rate: float) -> str:
    packet = {
        "section_id": group["section_id"],
        "concept_id": group["concept_id"],
        "misconception_tag": group["misconception_tag"],
        "attempt_count": group["attempt_count"],
        "wrong_count": group["wrong_count"],
        "misconception_rate": round(misconception_rate, 3),
        "diagnostic_purposes": sorted(set(group["diagnostic_purposes"]))[:8],
    }
    return f"""Summarize this aggregate checkpoint misunderstanding hotspot.

Use only aggregate evidence. Do not mention learners or learner IDs.

Hotspot packet:
{json.dumps(packet, ensure_ascii=False)}

Return JSON only with:
{json.dumps(HOTSPOT_SUMMARY_SCHEMA, ensure_ascii=False)}
"""


def _summarize_group(
    group: dict[str, Any],
    misconception_rate: float,
    llm_client: HotspotLLMClient | None,
) -> dict[str, str]:
    if llm_client is not None:
        payload = llm_client.generate_json(build_hotspot_summary_prompt(group, misconception_rate), HOTSPOT_SUMMARY_SCHEMA)
        return {
            "diagnostic_summary": _compact(payload.get("diagnostic_summary"), 420),
            "proposed_guidance": _compact(payload.get("proposed_guidance"), 420),
            "suggested_activity_adjustment": _compact(payload.get("suggested_activity_adjustment"), 320),
            "suggested_checkpoint_focus": _compact(payload.get("suggested_checkpoint_focus"), 320),
        }
    tag = str(group["misconception_tag"]).replace("_", " ")
    concept_id = str(group["concept_id"])
    return {
        "diagnostic_summary": (
            f"{group['wrong_count']} of {group['attempt_count']} attempts missed questions tagged '{tag}' "
            f"for {concept_id}."
        ),
        "proposed_guidance": f"Explicitly address the '{tag}' misunderstanding while teaching {concept_id}.",
        "suggested_activity_adjustment": f"Add a short contrast/check activity targeting '{tag}'.",
        "suggested_checkpoint_focus": f"Include checkpoint items that distinguish correct understanding from '{tag}'.",
    }


def _key(section_id: Any, concept_id: Any, misconception_tag: Any) -> tuple[str, str, str]:
    return (str(section_id or ""), str(concept_id or ""), str(misconception_tag or ""))


def _hotspot_id(group: dict[str, Any], window_start: str) -> str:
    raw = json.dumps(
        {
            "section_id": group["section_id"],
            "concept_id": group["concept_id"],
            "misconception_tag": group["misconception_tag"],
            "window_start": window_start,
        },
        sort_keys=True,
    )
    return "section_hotspot:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
