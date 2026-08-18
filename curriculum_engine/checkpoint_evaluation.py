"""LLM-owned checkpoint evaluation with strict, source-linked contracts."""

from __future__ import annotations

import json
from typing import Any, Protocol


class CheckpointEvaluationLLMClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return structured checkpoint evaluation JSON."""


CHECKPOINT_EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "recommendation": {"type": "string"},
        "overall_feedback": {"type": "string"},
        "question_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "is_correct": {"type": "boolean"},
                    "feedback": {"type": "string"},
                },
                "required": ["question_id", "is_correct", "feedback"],
            },
        },
    },
    "required": ["score", "recommendation", "overall_feedback", "question_results"],
}

VALID_RECOMMENDATIONS = {"continue", "review_module"}


def evaluate_checkpoint(
    llm_client: CheckpointEvaluationLLMClient,
    *,
    checkpoint_mcqs: list[dict[str, Any]],
    submitted_answers: list[dict[str, str]],
) -> dict[str, Any]:
    questions = _evaluation_questions(checkpoint_mcqs, submitted_answers)
    prompt = build_checkpoint_evaluation_prompt(questions)
    payload = llm_client.generate_json(prompt, CHECKPOINT_EVALUATION_SCHEMA)
    return checkpoint_evaluation_from_payload(payload, questions)


def build_checkpoint_evaluation_prompt(questions: list[dict[str, Any]]) -> str:
    packet = {"questions": questions}
    schema_example = {
        "score": 0.0,
        "recommendation": "continue|review_module",
        "overall_feedback": "short evidence-based summary",
        "question_results": [
            {
                "question_id": "exact question ID",
                "is_correct": True,
                "feedback": "short explanation of the learner's response",
            }
        ],
    }
    return f"""You evaluate a learner's checkpoint responses using the supplied answer keys and explanations.

Checkpoint evidence:
{json.dumps(packet, ensure_ascii=False)}

Evaluate the checkpoint now.

Critical rules:
- Return JSON only.
- Evaluate every question exactly once and preserve every question_id exactly.
- Use the supplied correct_option_id and explanation as the answer-key evidence.
- score must be between 0 and 1 and reflect the overall quality of the submitted responses.
- recommendation must be continue or review_module.
- Do not invent questions, sections, concepts, learner history, or additional assessment evidence.
- Keep question feedback and overall feedback concise and evidence based.

Required JSON shape:
{json.dumps(schema_example, ensure_ascii=False)}
"""


def checkpoint_evaluation_from_payload(
    payload: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = {row["question_id"]: row for row in questions}
    rows = payload.get("question_results")
    if not isinstance(rows, list):
        raise ValueError("Checkpoint evaluation response must include question_results")
    evaluated: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"question_results[{index}] must be an object")
        question_id = str(row.get("question_id") or "")
        if question_id not in expected:
            raise ValueError(f"Checkpoint evaluation returned unknown question_id: {question_id}")
        if question_id in evaluated:
            raise ValueError(f"Checkpoint evaluation returned duplicate question_id: {question_id}")
        if not isinstance(row.get("is_correct"), bool):
            raise ValueError(f"Checkpoint evaluation is_correct must be boolean for {question_id}")
        evaluated[question_id] = {
            "is_correct": row["is_correct"],
            "evaluation_feedback": _required_text(row.get("feedback"), f"feedback for {question_id}"),
        }
    missing = set(expected) - set(evaluated)
    if missing:
        raise ValueError(f"Checkpoint evaluation omitted question IDs: {sorted(missing)}")

    score = payload.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
        raise ValueError("Checkpoint evaluation score must be between 0 and 1")
    recommendation = str(payload.get("recommendation") or "").strip()
    if recommendation not in VALID_RECOMMENDATIONS:
        raise ValueError("Checkpoint evaluation recommendation must be continue or review_module")

    question_results = []
    for question in questions:
        judgment = evaluated[question["question_id"]]
        question_results.append(
            {
                "question_id": question["question_id"],
                "selected_option_id": question["selected_option_id"],
                "correct_option_id": question["correct_option_id"],
                "is_correct": judgment["is_correct"],
                "evaluation_feedback": judgment["evaluation_feedback"],
                "source_section_ids": question["source_section_ids"],
                "tested_concept_ids": question["tested_concept_ids"],
                "diagnostic_purpose": question["diagnostic_purpose"],
                "misconception_tags": question["misconception_tags"],
            }
        )
    return {
        "score": float(score),
        "recommendation": recommendation,
        "overall_feedback": _required_text(payload.get("overall_feedback"), "overall_feedback"),
        "question_results": question_results,
    }


def _evaluation_questions(
    checkpoint_mcqs: list[dict[str, Any]],
    submitted_answers: list[dict[str, str]],
) -> list[dict[str, Any]]:
    answer_by_id: dict[str, str] = {}
    for row in submitted_answers:
        question_id = str(row.get("question_id") or "")
        selected_option_id = str(row.get("selected_option_id") or "").upper()
        if not question_id or question_id in answer_by_id:
            raise ValueError("Checkpoint answers must contain unique, non-empty question IDs")
        answer_by_id[question_id] = selected_option_id

    expected_ids = {str(mcq.get("question_id") or "") for mcq in checkpoint_mcqs}
    unknown = set(answer_by_id) - expected_ids
    missing = expected_ids - set(answer_by_id)
    if unknown:
        raise ValueError(f"Checkpoint answers contain unknown question IDs: {sorted(unknown)}")
    if missing:
        raise ValueError(f"Checkpoint answers omitted question IDs: {sorted(missing)}")

    questions = []
    for mcq in checkpoint_mcqs:
        question_id = str(mcq.get("question_id") or "")
        options = mcq.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"Stored checkpoint question has invalid options: {question_id}")
        option_rows = []
        option_ids: set[str] = set()
        for option in options:
            if not isinstance(option, dict):
                raise ValueError(f"Stored checkpoint question has unstructured options: {question_id}")
            option_id = str(option.get("option_id") or "").upper()
            text = _required_text(option.get("text"), f"option text for {question_id}")
            if option_id not in {"A", "B", "C", "D"} or option_id in option_ids:
                raise ValueError(f"Stored checkpoint question has invalid option IDs: {question_id}")
            option_ids.add(option_id)
            option_rows.append({"option_id": option_id, "text": text})
        selected_option_id = answer_by_id[question_id]
        correct_option_id = str(mcq.get("correct_option_id") or "").upper()
        if selected_option_id not in option_ids:
            raise ValueError(f"Invalid selected_option_id for {question_id}: {selected_option_id}")
        if correct_option_id not in option_ids:
            raise ValueError(f"Invalid stored correct_option_id for {question_id}: {correct_option_id}")
        questions.append(
            {
                "question_id": question_id,
                "question": _required_text(mcq.get("question"), f"question text for {question_id}"),
                "options": option_rows,
                "selected_option_id": selected_option_id,
                "correct_option_id": correct_option_id,
                "answer_explanation": _required_text(mcq.get("explanation"), f"explanation for {question_id}"),
                "source_section_ids": [str(value) for value in mcq.get("source_section_ids") or []],
                "tested_concept_ids": [str(value) for value in mcq.get("tested_concept_ids") or []],
                "diagnostic_purpose": str(mcq.get("diagnostic_purpose") or ""),
                "misconception_tags": [str(value) for value in mcq.get("misconception_tags") or []],
            }
        )
    return questions


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Checkpoint evaluation requires {label}")
    return text
