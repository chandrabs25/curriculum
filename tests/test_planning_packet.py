from __future__ import annotations

import unittest

from curriculum_engine import OnboardingAnswers
from curriculum_engine.learning_path import LearningPathContext
from curriculum_engine.planning_packet import build_curriculum_planning_packet
from curriculum_engine.retrieval import SectionRetrievalResult


class PlanningPacketTest(unittest.TestCase):
    def onboarding(self) -> OnboardingAnswers:
        return OnboardingAnswers(
            subject="physics",
            topic="SI Units",
            current_level="beginner",
            confidence="low",
            learning_goal="understand units",
            available_time="2 hours",
            preferred_learning_style="worked examples",
            deadline_or_pace="steady",
        )

    def context(self) -> LearningPathContext:
        long_text = "Long evidence. " * 80
        section = {
            "section_id": "section:2",
            "chapter_id": "chapter:1",
            "title": "SI Units",
            "summary": "Summary. " * 120,
            "role": "target",
            "teaches": [
                {
                    "relationship_id": "rel:t",
                    "concept_id": "concept:si_units",
                    "label": "SI Units",
                    "confidence": 0.95,
                    "teaching_evidence": long_text,
                }
            ],
            "requires": [
                {
                    "relationship_id": "rel:r",
                    "concept_id": "concept:unit",
                    "label": "Unit",
                    "confidence": 0.9,
                    "pedagogical_reason": long_text,
                }
            ],
        }
        support = {
            "section_id": "section:3",
            "chapter_id": "chapter:1",
            "title": "Dimensional Analysis",
            "summary": "Support summary.",
            "relationship_id": "rel:s",
            "relationship_type": "TRANSFER_SUPPORTS_UNIT",
            "source_target_section_id": "section:2",
            "bridge_concept_id": "concept:dimensional_analysis",
            "confidence": 0.9,
            "evidence_text": long_text,
            "planning_meaning": "optional bridge",
            "use_as": "optional support while studying the main module",
        }
        reinforcement = {
            **support,
            "section_id": "section:4",
            "relationship_id": "rel:rf",
            "relationship_type": "RELATED_BY_CONCEPT",
            "use_as": "extra practice or comparison after the core module",
        }
        next_step = {
            **support,
            "section_id": "section:5",
            "relationship_id": "rel:n",
            "relationship_type": "DEPENDS_ON_UNIT",
            "use_as": "recommended next section after completing the module",
        }
        return LearningPathContext(
            main_path_sections=[section],
            target_sections=[section],
            prerequisite_sections=[],
            support_sections=[],
            prerequisite_check={"asked": True, "answers": [{"concept_id": "concept:unit", "status": "known_well"}]},
            parallel_support_paths=[support],
            reinforcement_paths=[reinforcement],
            next_step_paths=[next_step],
            cross_chapter_bridges=[support],
            relationship_policy={"hard_dependencies": "must affect ordering"},
            required_concepts=[{**section["requires"][0], "section_id": "section:2"}],
            taught_concepts=[{**section["teaches"][0], "section_id": "section:2"}],
            hard_dependency_edges=[
                {
                    "relationship_id": "rel:d",
                    "type": "DEPENDS_ON_UNIT",
                    "from_section_id": "section:2",
                    "to_section_id": "section:1",
                    "bridge_concept_id": "concept:unit",
                    "confidence": 0.9,
                    "evidence_text": long_text,
                    "evidence_reason": long_text,
                    "planning_meaning": "to_section should be studied before from_section",
                }
            ],
            optional_support_edges=[],
            learner_adjustments=[],
        )

    def test_packet_dedupes_and_preserves_section_link_reasoning(self) -> None:
        packet = build_curriculum_planning_packet(self.onboarding(), [], [], self.context()).to_dict()

        self.assertEqual(list(packet["sections_by_id"]).count("section:2"), 1)
        self.assertNotIn("concepts_by_id", packet)
        self.assertNotIn("requires_concept", packet["relationships"])
        self.assertNotIn("teaches_concept", packet["relationships"])
        self.assertNotIn("relationship_policy", packet)
        self.assertIn("prerequisite_check", packet)
        self.assertNotIn("matched_concept_ids", packet["sections_by_id"]["section:2"])
        self.assertIn("evidence_reason", packet["relationships"]["hard_dependencies"][0])
        self.assertLessEqual(len(packet["sections_by_id"]["section:2"]["summary"]), 420)
        self.assertIn("estimated_chars", packet["budget"])

    def test_packet_omits_empty_planner_context(self) -> None:
        context = self.context()
        context = LearningPathContext(
            main_path_sections=context.main_path_sections,
            target_sections=context.target_sections,
            prerequisite_sections=context.prerequisite_sections,
            support_sections=context.support_sections,
            prerequisite_check={"asked": False, "answers": []},
            parallel_support_paths=context.parallel_support_paths,
            reinforcement_paths=context.reinforcement_paths,
            next_step_paths=context.next_step_paths,
            cross_chapter_bridges=context.cross_chapter_bridges,
            relationship_policy=context.relationship_policy,
            required_concepts=context.required_concepts,
            taught_concepts=context.taught_concepts,
            hard_dependency_edges=context.hard_dependency_edges,
            optional_support_edges=context.optional_support_edges,
            learner_adjustments=context.learner_adjustments,
        )

        packet = build_curriculum_planning_packet(self.onboarding(), [], [], context).to_dict()

        self.assertNotIn("learner_state", packet)
        self.assertNotIn("prerequisite_check", packet)
        self.assertNotIn("relationship_policy", packet)
        self.assertNotIn("cross_chapter_bridges", packet["relationships"])

    def test_broad_context_keeps_top_six_ranked_targets_and_their_prerequisites(self) -> None:
        targets = [
            {
                "section_id": f"section:t{index}",
                "chapter_id": "chapter:1",
                "title": f"Target {index}",
                "summary": f"Target summary {index}",
                "role": "target",
                "score": float(index),
                "teaches": [],
                "requires": [],
            }
            for index in range(1, 9)
        ]
        prerequisite = {
            "section_id": "section:p1",
            "chapter_id": "chapter:1",
            "title": "Prerequisite",
            "summary": "A hard prerequisite.",
            "role": "prerequisite",
            "score": 0.0,
            "teaches": [],
            "requires": [],
        }
        support_sections = [
            {
                "section_id": f"section:s{index}",
                "chapter_id": "chapter:1",
                "title": f"Support {index}",
                "summary": "Optional support.",
                "role": "support",
                "score": 0.0,
                "teaches": [],
                "requires": [],
            }
            for index in range(1, 4)
        ]
        context = LearningPathContext(
            main_path_sections=[prerequisite, *targets],
            target_sections=targets,
            prerequisite_sections=[prerequisite],
            support_sections=support_sections,
            prerequisite_check={"asked": False, "answers": []},
            parallel_support_paths=[
                {
                    "section_id": "section:s1",
                    "chapter_id": "chapter:1",
                    "title": "Support 1",
                    "summary": "Optional support.",
                    "relationship_id": "rel:s",
                    "relationship_type": "TRANSFER_SUPPORTS_UNIT",
                    "source_target_section_id": "section:t8",
                    "confidence": 0.9,
                }
            ],
            reinforcement_paths=[],
            next_step_paths=[],
            cross_chapter_bridges=[],
            relationship_policy={"hard_dependencies": "must affect ordering"},
            required_concepts=[],
            taught_concepts=[],
            hard_dependency_edges=[
                {
                    "relationship_id": "rel:selected",
                    "type": "DEPENDS_ON_UNIT",
                    "from_section_id": "section:t8",
                    "to_section_id": "section:p1",
                    "confidence": 0.9,
                    "evidence_reason": "Target 8 needs the prerequisite.",
                },
                {
                    "relationship_id": "rel:unselected",
                    "type": "DEPENDS_ON_UNIT",
                    "from_section_id": "section:t1",
                    "to_section_id": "section:p1",
                    "confidence": 0.9,
                },
            ],
            optional_support_edges=[],
            learner_adjustments=[],
        )
        retrieved = [
            SectionRetrievalResult(
                section_id=f"section:t{index}",
                chapter_id="chapter:1",
                title=f"Target {index}",
                summary=f"Target summary {index}",
                score=float(index),
                matched_concept_ids=[f"concept:t{index}"],
                reasons=["vector_match"],
            )
            for index in range(1, 9)
        ]

        packet = build_curriculum_planning_packet(self.onboarding(), [], retrieved, context).to_dict()

        self.assertTrue(packet["budget"]["broad_section_selection"])
        self.assertEqual(packet["budget"]["input_section_count"], 12)
        self.assertEqual(packet["budget"]["selected_target_section_count"], 6)
        self.assertEqual(packet["main_path_section_ids"], [
            "section:p1",
            "section:t8",
            "section:t7",
            "section:t6",
            "section:t5",
            "section:t4",
            "section:t3",
        ])
        self.assertEqual(set(packet["sections_by_id"]), set(packet["main_path_section_ids"]))
        self.assertEqual(packet["relationships"]["parallel_support"], [])
        self.assertEqual(packet["relationships"]["reinforcement"], [])
        self.assertEqual(packet["relationships"]["next_steps"], [])
        self.assertNotIn("cross_chapter_bridges", packet["relationships"])
        self.assertEqual(
            [row["relationship_id"] for row in packet["relationships"]["hard_dependencies"]],
            ["rel:selected"],
        )
        for section in packet["sections_by_id"].values():
            self.assertNotIn("matched_concept_ids", section)


if __name__ == "__main__":
    unittest.main()
