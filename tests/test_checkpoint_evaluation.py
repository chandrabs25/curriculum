from __future__ import annotations

import unittest
from typing import Any

from curriculum_engine.checkpoint_evaluation import evaluate_checkpoint


def checkpoint_question() -> dict[str, Any]:
    return {
        "question_id": "module:1:q1",
        "question": "Which statement is correct?",
        "options": [
            {"option_id": "A", "text": "The grounded statement"},
            {"option_id": "B", "text": "A distractor"},
            {"option_id": "C", "text": "Another distractor"},
            {"option_id": "D", "text": "A final distractor"},
        ],
        "correct_option_id": "A",
        "explanation": "The source summary supports option A.",
        "source_section_ids": ["section:1"],
        "tested_concept_ids": ["concept:one"],
        "diagnostic_purpose": "Checks the central distinction.",
        "misconception_tags": ["confuses_distinction"],
    }


class FakeEvaluationLLM:
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.prompt = ""
        self.schema: dict[str, Any] | None = None

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.prompt = prompt
        self.schema = schema
        return self.response


class CheckpointEvaluationTest(unittest.TestCase):
    def test_llm_owns_score_and_question_judgment(self) -> None:
        llm = FakeEvaluationLLM(
            {
                "score": 0.8,
                "recommendation": "continue",
                "overall_feedback": "The response demonstrates the central distinction.",
                "question_results": [
                    {
                        "question_id": "module:1:q1",
                        "is_correct": True,
                        "feedback": "The selected answer matches the supplied evidence.",
                    }
                ],
            }
        )

        result = evaluate_checkpoint(
            llm,
            checkpoint_mcqs=[checkpoint_question()],
            submitted_answers=[{"question_id": "module:1:q1", "selected_option_id": "A"}],
        )

        self.assertEqual(result["score"], 0.8)
        self.assertTrue(result["question_results"][0]["is_correct"])
        self.assertEqual(result["question_results"][0]["source_section_ids"], ["section:1"])
        self.assertIn('"correct_option_id": "A"', llm.prompt)
        self.assertIsNotNone(llm.schema)

    def test_missing_answer_is_rejected_before_llm_call(self) -> None:
        llm = FakeEvaluationLLM({})

        with self.assertRaisesRegex(ValueError, "omitted question IDs"):
            evaluate_checkpoint(llm, checkpoint_mcqs=[checkpoint_question()], submitted_answers=[])

        self.assertEqual(llm.prompt, "")

    def test_unknown_question_result_is_rejected(self) -> None:
        llm = FakeEvaluationLLM(
            {
                "score": 1.0,
                "recommendation": "continue",
                "overall_feedback": "Feedback.",
                "question_results": [
                    {"question_id": "module:1:unknown", "is_correct": True, "feedback": "Feedback."}
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "unknown question_id"):
            evaluate_checkpoint(
                llm,
                checkpoint_mcqs=[checkpoint_question()],
                submitted_answers=[{"question_id": "module:1:q1", "selected_option_id": "A"}],
            )


if __name__ == "__main__":
    unittest.main()
