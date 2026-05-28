from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from curriculum_engine import (
    ArtifactStore,
    CurriculumGraph,
    CurriculumRetriever,
    TextbookStore,
    build_intent_classification_packet,
    build_intent_classification_prompt,
    intent_classification_from_payload,
)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class IntentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        chapter_path = Path("data/textbook_sources/physics/grade_11/ch2.json")
        write_json(
            self.root / "data/textbook_sources/manifest.json",
            {
                "chapters": [
                    {
                        "id": "chapter:2",
                        "subject": "physics",
                        "grade": 11,
                        "chapter_number": 2,
                        "chapter_title": "Motion in a Straight Line",
                        "path": str(chapter_path),
                    }
                ]
            },
        )
        write_json(
            self.root / chapter_path,
            {
                "id": "chapter:2",
                "subject": "physics",
                "grade": 11,
                "chapter": {
                    "id": "chapter:2",
                    "title": "Motion in a Straight Line",
                    "sections": [
                        {"id": "section:2.3", "number": "2.3", "title": "ACCELERATION", "content_text": "", "subsections": []},
                        {"id": "section:2.4", "number": "2.4", "title": "Acceleration Due to Gravity", "content_text": "", "subsections": []},
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_json(self.root / "data/relationship_artifacts/usable_chapters.json", {"usable_chapter_ids": ["chapter:2"]})
        write_jsonl(
            self.root / "data/relationship_artifacts/section_summaries.jsonl",
            [
                {"chapter_id": "chapter:2", "section_id": "section:2.3", "title": "ACCELERATION", "summary": "Defines acceleration.", "key_terms": ["acceleration"]},
                {"chapter_id": "chapter:2", "section_id": "section:2.4", "title": "Acceleration Due to Gravity", "summary": "Explains g.", "key_terms": ["acceleration", "gravity"]},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [
                {"concept_id": "concept:acceleration", "canonical_label": "Acceleration", "normalized_label": "acceleration", "aliases": []},
                {"concept_id": "concept:acceleration_due_to_gravity", "canonical_label": "Acceleration Due To Gravity", "normalized_label": "acceleration_due_to_gravity", "aliases": []},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:2", "type": "TEACHES_CONCEPT", "from_id": "section:2.3", "to_id": "concept:acceleration"},
                {"chapter_id": "chapter:2", "type": "TEACHES_CONCEPT", "from_id": "section:2.4", "to_id": "concept:acceleration_due_to_gravity"},
            ],
        )
        self.graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root), usable_only=True)
        self.retriever = CurriculumRetriever(self.graph)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_packet_uses_only_titles_and_concepts(self) -> None:
        packet = build_intent_classification_packet(self.graph, self.retriever, "acceleration").to_dict()

        self.assertEqual(packet["original_query"], "acceleration")
        self.assertTrue(packet["matched_concepts"])
        self.assertTrue(packet["candidate_sections"])
        self.assertIn("title", packet["candidate_sections"][0])
        self.assertNotIn("summary", packet["candidate_sections"][0])

    def test_prompt_tells_llm_not_to_copy_section_titles(self) -> None:
        prompt = build_intent_classification_prompt(
            build_intent_classification_packet(self.graph, self.retriever, "acceleration")
        )

        self.assertIn("Do not copy section titles as option labels", prompt)
        self.assertLess(prompt.index("Intent packet:"), prompt.index("Final task:"))

    def test_parse_confirmed_intent(self) -> None:
        packet = build_intent_classification_packet(self.graph, self.retriever, "acceleration")
        result = intent_classification_from_payload(
            {
                "needs_user_choice": False,
                "question": "",
                "confirmed_label": "Understand what acceleration means",
                "confirmed_summary": "Learn acceleration as change in velocity over time.",
                "refined_query": "basic meaning of acceleration as rate of change of velocity",
                "grounding_section_ids": ["section:2.3", "missing"],
                "options": [],
            },
            packet,
        )

        self.assertEqual(result["status"], "confirmed")
        self.assertNotIn("intent_id", result["confirmed_intent"])
        self.assertEqual(result["confirmed_intent"]["grounding_section_ids"], ["section:2.3"])

    def test_parse_clarification_options(self) -> None:
        packet = build_intent_classification_packet(self.graph, self.retriever, "acceleration")
        result = intent_classification_from_payload(
            {
                "needs_user_choice": True,
                "question": "What kind of acceleration do you want to learn?",
                "confirmed_label": "",
                "confirmed_summary": "",
                "refined_query": "",
                "grounding_section_ids": [],
                "options": [
                    {
                        "label": "Understand what acceleration means",
                        "user_facing_description": "Learn acceleration as change in velocity over time.",
                        "refined_query": "basic meaning of acceleration",
                        "grounding_section_ids": ["section:2.3"],
                    },
                    {
                        "label": "Learn acceleration due to gravity",
                        "user_facing_description": "Understand what g means for falling objects.",
                        "refined_query": "acceleration due to gravity",
                        "grounding_section_ids": ["section:2.4"],
                    },
                ],
            },
            packet,
        )

        self.assertTrue(result["needs_user_choice"])
        self.assertEqual(len(result["options"]), 2)
        self.assertNotIn("intent_id", result["options"][0])
        self.assertNotIn("intent_id", result["options"][1])

    def test_ignores_invalid_model_status_and_derives_from_shape(self) -> None:
        packet = build_intent_classification_packet(self.graph, self.retriever, "acceleration")
        result = intent_classification_from_payload(
            {
                "status": "clear_enough",
                "needs_user_choice": False,
                "question": "",
                "confirmed_label": "Understand what acceleration means",
                "confirmed_summary": "Learn acceleration as change in velocity over time.",
                "refined_query": "basic meaning of acceleration",
                "grounding_section_ids": ["section:2.3"],
                "options": [],
            },
            packet,
        )

        self.assertEqual(result["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
