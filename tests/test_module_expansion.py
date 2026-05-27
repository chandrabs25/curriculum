from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from curriculum_engine import (
    allocate_module_mcq_targets,
    PlannedCurriculumModule,
    CurriculumPlan,
    ModuleExpander,
    OnboardingAnswers,
    TextbookStore,
    fetch_full_source_sections,
    build_module_expansion_packet,
)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def mcq_rows(count: int) -> list[dict[str, Any]]:
    return [
        {
            "question_id": f"module:2:q{index}",
            "question": f"Which statement about SI units is correct? {index}",
            "options": [
                "A. SI units create shared standards",
                "B. SI units remove all measurement",
                "C. SI units replace physical quantities",
                "D. SI units avoid calculations entirely",
            ],
            "correct_option": "A",
            "explanation": "The summary connects SI units with standard base units.",
            "tested_concept_ids": ["concept:si_units"],
            "source_section_ids": ["section:2"],
            "difficulty": "medium",
            "diagnostic_purpose": "Checks whether the learner understands SI units as standards.",
            "misconception_tags": ["treats_units_as_quantities"],
        }
        for index in range(1, count + 1)
    ]


class FakeExpansionLLM:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.prompt = ""
        self.schema = None

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.prompt = prompt
        self.schema = schema
        return self.payload


class ModuleExpansionTest(unittest.TestCase):
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
                        {
                            "id": "section:1",
                            "number": "1.1",
                            "title": "Units",
                            "content_text": "Units describe measurement standards.",
                            "subsections": [],
                        },
                        {
                            "id": "section:2",
                            "number": "1.2",
                            "title": "SI Units",
                            "content_text": "SI units define standard base units.",
                            "subsections": [
                                {
                                    "id": "section:2:1",
                                    "title": "Base units",
                                    "content_type": "definition",
                                    "content_text": "The metre, kilogram, and second are base units.",
                                    "worked_examples": [{"id": "ex:1", "text": "Classify metre as a base unit."}],
                                    "diagrams": [{"id": "fig:1", "caption": "Base unit chart"}],
                                    "tables": [{"id": "tbl:1", "caption": "SI base quantities"}],
                                }
                            ],
                        },
                        {
                            "id": "section:3",
                            "number": "1.3",
                            "title": "Applications",
                            "content_text": "Applications use SI units.",
                            "subsections": [],
                        },
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/section_summaries.jsonl",
            [
                {"chapter_id": "chapter:1", "section_id": "section:1", "title": "Units", "summary": "Defines measurement units.", "key_terms": ["unit"]},
                {
                    "chapter_id": "chapter:1",
                    "section_id": "section:2",
                    "section_number": "1.2",
                    "title": "SI Units",
                    "summary": "Introduces SI base units and why standards matter.",
                    "key_terms": ["SI", "base unit"],
                    "candidate_concept_ids": ["concept:si_units"],
                    "covered_subsection_ids": ["section:2:1"],
                },
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
                {
                    "chapter_id": "chapter:1",
                    "type": "TEACHES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:si_units",
                    "teaching_evidence": "This section teaches SI base units.",
                    "evidence": {"text": "This section teaches SI base units."},
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "REQUIRES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:unit",
                    "pedagogical_reason": "The learner should know what a unit is first.",
                    "evidence": {"text": "The learner should know what a unit is first."},
                },
            ],
        )
        self.plan = CurriculumPlan(
            curriculum_plan_id="plan:1",
            learner_id="learner:1",
            onboarding=OnboardingAnswers(
                subject="physics",
                topic="SI Units",
                current_level="beginner",
                confidence="low",
                learning_goal="use units in physics problems",
                available_time="2 hours",
                preferred_learning_style="worked examples",
                deadline_or_pace="steady",
            ),
            modules=[
                PlannedCurriculumModule(
                    module_id="module:1",
                    title="Units",
                    module_goal="Understand units.",
                    position=1,
                    covered_concept_ids=["concept:unit"],
                    source_section_ids=["section:1"],
                ),
                PlannedCurriculumModule(
                    module_id="module:2",
                    title="SI Units",
                    module_goal="Use SI units.",
                    position=2,
                    covered_concept_ids=["concept:si_units"],
                    source_section_ids=["section:2"],
                    link_from_previous="Units prepare SI standards.",
                    link_to_next="SI standards support applications.",
                ),
                PlannedCurriculumModule(
                    module_id="module:3",
                    title="Applications",
                    module_goal="Apply SI units.",
                    position=3,
                    covered_concept_ids=["concept:application"],
                    source_section_ids=["section:3"],
                ),
            ],
            created_at=datetime.now(timezone.utc),
            metadata={
                "planning_packet": {
                    "relationships": {
                        "requires_concept": [
                            {
                                "from_section_id": "section:2",
                                "to_concept_id": "concept:unit",
                                "pedagogical_reason": "Units are needed before SI standards.",
                            }
                        ],
                        "teaches_concept": [
                            {
                                "from_section_id": "section:2",
                                "to_concept_id": "concept:si_units",
                                "teaching_evidence": "SI units define base units.",
                            }
                        ],
                    }
                }
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_packet_includes_summary_current_source_and_compact_neighbors(self) -> None:
        packet = build_module_expansion_packet(
            TextbookStore(self.root),
            self.plan,
            self.plan.modules[1],
        ).to_dict()

        self.assertEqual(packet["source_mode"], "summary")
        self.assertEqual(packet["module"]["module_id"], "module:2")
        self.assertEqual(packet["previous_module"]["module_id"], "module:1")
        self.assertEqual(packet["next_module"]["module_id"], "module:3")
        self.assertNotIn("content_text", packet["previous_module"])
        self.assertEqual(packet["previous_module"]["link_to_next"], "")
        self.assertEqual(packet["source_sections"][0]["section_id"], "section:2")
        self.assertEqual(packet["source_sections"][0]["summary"], "Introduces SI base units and why standards matter.")
        self.assertEqual(packet["source_sections"][0]["key_terms"], ["SI", "base unit"])
        self.assertEqual(packet["source_sections"][0]["candidate_concept_ids"], ["concept:si_units"])
        self.assertEqual(packet["mcq_target_count"], 4)
        self.assertNotIn("content_text", packet["source_sections"][0])
        self.assertNotIn("subsections", packet["source_sections"][0])
        self.assertGreater(packet["source_sections"][0]["resource_counts"]["worked_examples"], 0)
        self.assertEqual(packet["target_concepts"][0]["concept_id"], "concept:si_units")
        self.assertEqual(
            packet["relationship_reasoning"]["requires_concept"][0]["pedagogical_reason"],
            "Units are needed before SI standards.",
        )

    def test_full_source_helper_fetches_text_outside_module_design(self) -> None:
        rows = fetch_full_source_sections(TextbookStore(self.root), ["section:2"])

        self.assertIn("SI units define standard base units.", rows[0]["content_text"])
        self.assertIn("The metre, kilogram, and second", rows[0]["subsections"][0]["content_text"])

    def test_target_concepts_come_from_graph_when_module_concepts_are_empty(self) -> None:
        module = PlannedCurriculumModule(
            module_id="module:empty",
            title="SI Units",
            module_goal="Use SI units.",
            position=2,
            covered_concept_ids=[],
            source_section_ids=["section:2"],
        )
        plan = CurriculumPlan(
            curriculum_plan_id="plan:2",
            learner_id="learner:1",
            onboarding=self.plan.onboarding,
            modules=[module],
            created_at=self.plan.created_at,
            metadata={},
        )

        packet = build_module_expansion_packet(TextbookStore(self.root), plan, module).to_dict()
        concept_ids = {row["concept_id"] for row in packet["target_concepts"]}

        self.assertIn("concept:si_units", concept_ids)
        self.assertIn("concept:unit", concept_ids)

    def test_allocates_plan_level_mcqs_by_module_size(self) -> None:
        plan = CurriculumPlan(
            curriculum_plan_id="plan:weighted",
            learner_id="learner:1",
            onboarding=self.plan.onboarding,
            modules=[
                PlannedCurriculumModule(
                    module_id="module:small",
                    title="Small",
                    module_goal="Learn one section.",
                    position=1,
                    covered_concept_ids=[],
                    source_section_ids=["section:1"],
                ),
                PlannedCurriculumModule(
                    module_id="module:large",
                    title="Large",
                    module_goal="Learn two sections.",
                    position=2,
                    covered_concept_ids=[],
                    source_section_ids=["section:2", "section:3"],
                ),
                PlannedCurriculumModule(
                    module_id="module:medium",
                    title="Medium",
                    module_goal="Learn one section.",
                    position=3,
                    covered_concept_ids=[],
                    source_section_ids=["section:1"],
                ),
            ],
            created_at=self.plan.created_at,
            metadata={},
        )

        allocation = allocate_module_mcq_targets(plan)

        self.assertGreaterEqual(sum(allocation.values()), 10)
        self.assertLessEqual(sum(allocation.values()), 12)
        self.assertTrue(all(count >= 1 for count in allocation.values()))
        self.assertGreater(allocation["module:large"], allocation["module:small"])

    def test_expander_creates_grounded_module_and_mcq(self) -> None:
        module_without_concepts = PlannedCurriculumModule(
            module_id="module:2",
            title="SI Units",
            module_goal="Use SI units.",
            position=2,
            covered_concept_ids=[],
            source_section_ids=["section:2"],
            link_from_previous="Units prepare SI standards.",
            link_to_next="SI standards support applications.",
        )
        plan = CurriculumPlan(
            curriculum_plan_id="plan:conceptless",
            learner_id="learner:1",
            onboarding=self.plan.onboarding,
            modules=[module_without_concepts],
            created_at=self.plan.created_at,
            metadata={},
        )
        llm = FakeExpansionLLM(
            {
                "title": "SI Units",
                "module_goal": "Use SI units.",
                "larger_goal_alignment": "SI units help solve physics problems consistently.",
                "transition_from_previous": "Units prepare SI standards.",
                "transition_to_next": "SI standards support applications.",
                "lesson_sections": [
                    {
                        "heading": "Base SI units",
                        "body": "Use metre, kilogram, and second as standards.",
                        "source_section_ids": ["section:2"],
                        "concept_ids": ["concept:si_units"],
                    }
                ],
                "guided_activity": "Make a table of base units.",
                "common_misconceptions": ["Confusing a quantity with its unit."],
                "checkpoint_mcqs": mcq_rows(12),
            }
        )

        expanded = ModuleExpander(TextbookStore(self.root), llm).expand_module(plan, "module:2")

        self.assertEqual(expanded.module_id, "module:2")
        self.assertEqual(expanded.lesson_sections[0]["source_section_ids"], ["section:2"])
        self.assertEqual(expanded.lesson_sections[0]["concept_ids"], ["concept:si_units"])
        self.assertEqual(len(expanded.checkpoint_mcqs), 12)
        self.assertEqual(expanded.checkpoint_mcqs[0].correct_option, "A")
        self.assertEqual(expanded.checkpoint_mcqs[0].source_section_ids, ["section:2"])
        self.assertEqual(expanded.checkpoint_mcqs[0].tested_concept_ids, ["concept:si_units"])
        self.assertEqual(expanded.checkpoint_mcqs[0].question_id, "module:2:q1")
        self.assertEqual(expanded.checkpoint_mcqs[0].difficulty, "medium")
        self.assertEqual(expanded.checkpoint_mcqs[0].diagnostic_purpose, "Checks whether the learner understands SI units as standards.")
        self.assertEqual(expanded.checkpoint_mcqs[0].misconception_tags, ["treats_units_as_quantities"])
        self.assertIn("concept:si_units", expanded.concept_ids)
        self.assertIn("Module design packet:", llm.prompt)
        self.assertIn("checkpoint_mcqs", llm.prompt)
        self.assertIn("diagnostic_purpose", llm.prompt)
        self.assertIn('"source_mode": "summary"', llm.prompt)
        self.assertNotIn("SI units define standard base units.", llm.prompt)
        self.assertNotIn("The metre, kilogram, and second", llm.prompt)
        self.assertLess(llm.prompt.index("Module design packet:"), llm.prompt.index("Critical rules:"))
        self.assertIsNotNone(llm.schema)
        self.assertIn("checkpoint_mcqs", llm.schema["required"])

    def test_legacy_single_checkpoint_mcq_is_rejected(self) -> None:
        llm = FakeExpansionLLM(
            {
                "title": "SI Units",
                "module_goal": "Use SI units.",
                "larger_goal_alignment": "SI units help solve physics problems consistently.",
                "lesson_sections": [
                    {
                        "heading": "Base SI units",
                        "body": "Use SI units as shared standards.",
                        "source_section_ids": ["section:2"],
                        "concept_ids": ["concept:si_units"],
                    }
                ],
                "guided_activity": "Make a table of base units.",
                "checkpoint_mcq": {
                    "question": "Which option lists SI base units?",
                    "options": ["A. metre, kilogram, second", "B. litre, hour", "C. mile, foot", "D. pound, ounce"],
                    "correct_option": "A",
                    "explanation": "The summary names standard base units.",
                    "tested_concept_ids": ["concept:si_units"],
                    "source_section_ids": ["section:2"],
                },
            }
        )

        with self.assertRaises(ValueError):
            ModuleExpander(TextbookStore(self.root), llm).expand_module(self.plan, "module:2")

    def test_invalid_mcq_concepts_are_rejected(self) -> None:
        llm = FakeExpansionLLM(
            {
                "title": "SI Units",
                "module_goal": "Use SI units.",
                "larger_goal_alignment": "SI units help solve physics problems consistently.",
                "lesson_sections": [
                    {
                        "heading": "Base SI units",
                        "body": "Use SI units as shared standards.",
                        "source_section_ids": ["section:2"],
                        "concept_ids": ["concept:si_units"],
                    }
                ],
                "guided_activity": "Make a table of base units.",
                "checkpoint_mcqs": [
                    {
                        "question_id": "module:2:q1",
                        "question": "Which statement is correct?",
                        "options": ["A. SI units are standards", "B. Units are never used", "C. Standards are optional", "D. Quantities are units"],
                        "correct_option": "A",
                        "explanation": "The module summary introduces SI standards.",
                        "tested_concept_ids": ["concept:missing"],
                        "source_section_ids": ["section:2"],
                        "difficulty": "medium",
                        "diagnostic_purpose": "Checks whether the learner understands SI units as standards.",
                        "misconception_tags": ["treats_units_as_quantities"],
                    }
                ]
                + mcq_rows(3),
            }
        )

        with self.assertRaises(ValueError):
            ModuleExpander(TextbookStore(self.root), llm).expand_module(self.plan, "module:2")


if __name__ == "__main__":
    unittest.main()
