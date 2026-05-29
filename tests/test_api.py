from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from curriculum_engine.api import CurriculumAPIService, create_app


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.prompts.append(prompt)
        if schema and "needs_user_choice" in schema.get("properties", {}):
            return {
                "needs_user_choice": False,
                "question": "",
                "confirmed_label": "Learn SI units",
                "confirmed_summary": "You want to learn SI measurement standards.",
                "refined_query": "SI units and measurement standards",
                "options": [],
            }
        if schema and "modules" in schema.get("properties", {}):
            return {
                "modules": [
                    {
                        "module_id": "module:si",
                        "title": "SI Unit Foundations",
                        "module_goal": "Use SI units with confidence.",
                        "position": 1,
                        "depends_on_module_ids": [],
                        "link_from_previous": "",
                        "link_to_next": "Use SI units in applications.",
                        "source_section_ids": ["section:2"],
                        "prerequisite_warnings": ["Review units first."],
                        "parallel_support_section_ids": ["section:3"],
                        "reinforcement_section_ids": [],
                        "next_step_section_ids": [],
                    }
                ]
            }
        if schema and "section_insights" in schema.get("properties", {}):
            return {
                "section_insights": [
                    {
                        "section_id": "section:2",
                        "understanding_summary": "The learner understands SI units as shared standards.",
                        "current_status": "competent",
                        "strengths": ["Recognizes SI units as standards."],
                        "misconceptions_or_gaps": [],
                        "recommended_adjustment": "Keep explanations concise and move toward applications.",
                        "confidence": 0.9,
                        "evidence_question_ids": ["module:si:q1"],
                        "supersedes_insight_id": "section_insight:old",
                        "reconciliation_reason": "New correct answers supersede the prior partial insight.",
                    }
                ]
            }
        count_match = re.search(r'"mcq_target_count":\s*(\d+)', prompt)
        count = int(count_match.group(1)) if count_match else 1
        return {
            "title": "SI Unit Foundations",
            "module_goal": "Use SI units with confidence.",
            "larger_goal_alignment": "This supports the learner's measurement goal.",
            "transition_from_previous": "",
            "transition_to_next": "This prepares applications.",
            "lesson_sections": [
                {
                    "heading": "SI units",
                    "body": "Use SI units as shared measurement standards.",
                    "source_section_ids": ["section:2"],
                    "concept_ids": ["concept:si_units"],
                }
            ],
            "guided_activity": "Make a table of common SI base units.",
            "common_misconceptions": ["Treating a quantity as the same thing as its unit."],
            "checkpoint_mcqs": [
                {
                    "question_id": f"module:si:q{index}",
                    "question": f"Which statement about SI units is correct? {index}",
                    "options": [
                        "A. SI units create shared standards",
                        "B. SI units remove measurement",
                        "C. SI units replace physical quantities",
                        "D. SI units avoid calculations",
                    ],
                    "correct_option": "A",
                    "explanation": "SI units are shared measurement standards.",
                    "tested_concept_ids": ["concept:si_units"],
                    "source_section_ids": ["section:2"],
                    "difficulty": "medium",
                    "diagnostic_purpose": "Checks whether the learner understands SI units as standards.",
                    "misconception_tags": ["treats_units_as_quantities"],
                }
                for index in range(1, count + 1)
            ],
        }


class APITest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        chapter_path = Path("data/textbook_sources/physics/grade_11/ch1.json")
        write_json(
            self.root / "data/textbook_sources/manifest.json",
            {
                "chapters": [
                    {
                        "id": "chapter:1",
                        "subject": "physics",
                        "grade": 11,
                        "chapter_number": 1,
                        "chapter_title": "Measurement",
                        "path": str(chapter_path),
                    }
                ]
            },
        )
        write_json(
            self.root / chapter_path,
            {
                "id": "chapter:1",
                "subject": "physics",
                "grade": 11,
                "chapter": {
                    "id": "chapter:1",
                    "title": "Measurement",
                    "sections": [
                        {"id": "section:1", "number": "1.1", "title": "Units", "content_text": "", "subsections": []},
                        {"id": "section:2", "number": "1.2", "title": "SI Units", "content_text": "", "subsections": []},
                        {"id": "section:3", "number": "1.3", "title": "Applications", "content_text": "", "subsections": []},
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_json(
            self.root / "data/relationship_artifacts/usable_chapters.json",
            {"usable_chapter_ids": ["chapter:1"]},
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/section_summaries.jsonl",
            [
                {"chapter_id": "chapter:1", "section_id": "section:1", "title": "Units", "summary": "Defines units.", "key_terms": ["unit"]},
                {"chapter_id": "chapter:1", "section_id": "section:2", "title": "SI Units", "summary": "Introduces SI units.", "key_terms": ["SI"]},
                {"chapter_id": "chapter:1", "section_id": "section:3", "title": "Applications", "summary": "Applies SI units.", "key_terms": ["application"]},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [
                {"concept_id": "concept:unit", "canonical_label": "Unit", "normalized_label": "unit", "aliases": []},
                {"concept_id": "concept:si_units", "canonical_label": "SI Units", "normalized_label": "si_units", "aliases": []},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:1", "to_id": "concept:unit"},
                {
                    "chapter_id": "chapter:1",
                    "type": "TEACHES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:si_units",
                    "teaching_evidence": "SI units are introduced.",
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "REQUIRES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:unit",
                    "pedagogical_reason": "Learners should understand units first.",
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "DEPENDS_ON_UNIT",
                    "from_id": "section:2",
                    "to_id": "section:1",
                    "source_concept_id": "concept:unit",
                    "evidence": {"text": "SI units depend on units.", "reason": "dependency"},
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "TRANSFER_SUPPORTS_UNIT",
                    "from_id": "section:2",
                    "to_id": "section:3",
                    "source_concept_id": "concept:si_units",
                    "evidence": {"text": "Applications support SI units.", "reason": "support"},
                },
            ],
        )
        self.fake_llm = FakeLLM()
        service = CurriculumAPIService(root=self.root, use_vector=False, llm_client=self.fake_llm, intent_llm_client=self.fake_llm)
        self.client = TestClient(create_app(service))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def query_payload(self) -> dict[str, Any]:
        return {
            "learner_id": "learner:1",
            "onboarding": {
                "subject": "physics",
                "topic": "SI Units",
                "current_level": "beginner",
                "confidence": "low",
                "learning_goal": "solve measurement problems",
                "available_time": "2 hours",
                "preferred_learning_style": "worked examples",
                "deadline_or_pace": "steady",
            },
            "grade": 11,
        }

    def test_retrieval_preview_endpoint(self) -> None:
        response = self.client.post("/api/retrieval/preview", json=self.query_payload())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["retrieved_sections"])
        self.assertIn("planning_packet", data)
        self.assertEqual(data["prerequisite_questions"], [])

    def test_intent_classification_endpoint(self) -> None:
        response = self.client.post("/api/intent/classify", json={"query": "SI Units", "grade": 11})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "confirmed")
        self.assertFalse(data["needs_user_choice"])
        self.assertEqual(data["confirmed_intent"]["refined_query"], "SI units and measurement standards")
        self.assertIn("classification_packet", data)

    def test_plan_module_design_and_checkpoint_submit_endpoints(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()
        self.assertEqual(plan["modules"][0]["module_id"], "module:si")
        self.assertIn("mcq_allocation", plan)

        design_response = self.client.post(
            "/api/modules/design",
            json={"plan": plan, "module_id": "module:si"},
        )
        self.assertEqual(design_response.status_code, 200)
        module = design_response.json()
        self.assertEqual(len(module["checkpoint_mcqs"]), plan["mcq_allocation"]["module:si"])

        submit_response = self.client.post(
            "/api/checkpoints/submit",
            json={
                "learner_id": "learner:1",
                "curriculum_plan_id": plan["curriculum_plan_id"],
                "module_id": "module:si",
                "checkpoint_mcqs": module["checkpoint_mcqs"],
                "existing_section_insights": [
                    {
                        "insight_id": "section_insight:old",
                        "learner_id": "learner:1",
                        "curriculum_plan_id": plan["curriculum_plan_id"],
                        "module_id": "module:old",
                        "section_id": "section:2",
                        "understanding_summary": "The learner had partial understanding of SI units.",
                        "current_status": "partial_understanding",
                        "strengths": [],
                        "misconceptions_or_gaps": ["Confuses quantities and units."],
                        "recommended_adjustment": "Review SI units carefully.",
                        "confidence": 0.7,
                        "evidence_question_ids": ["old:q1"],
                        "reconciliation_reason": "Prior checkpoint evidence.",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
                "answers": [
                    {"question_id": mcq["question_id"], "selected_option": "A"}
                    for mcq in module["checkpoint_mcqs"]
                ],
            },
        )
        self.assertEqual(submit_response.status_code, 200)
        result = submit_response.json()
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["insight_events"])
        self.assertEqual(result["section_insights"][0]["section_id"], "section:2")
        self.assertEqual(result["section_insights"][0]["supersedes_insight_id"], "section_insight:old")
        self.assertTrue(any("existing_section_insights" in prompt for prompt in self.fake_llm.prompts))


if __name__ == "__main__":
    unittest.main()
