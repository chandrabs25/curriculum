from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from curriculum_engine import ArtifactStore, CurriculumGraph, TextbookStore


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class CurriculumGraphTest(unittest.TestCase):
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
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/section_summaries.jsonl",
            [
                {"chapter_id": "chapter:1", "section_id": "section:1", "title": "Units", "summary": "Defines units.", "key_terms": ["unit"]},
                {"chapter_id": "chapter:1", "section_id": "section:2", "title": "SI Units", "summary": "Introduces SI units.", "key_terms": ["SI"]},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [{"concept_id": "concept:unit", "canonical_label": "Unit"}],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:1", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "DEPENDS_ON_UNIT", "from_id": "section:2", "to_id": "section:1"},
                {"chapter_id": "chapter:1", "type": "REQUIRES_CONCEPT", "from_id": "section:2", "to_id": "concept:unit"},
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_textbook_store_loads_section_ids(self) -> None:
        store = TextbookStore(self.root)
        self.assertEqual(store.section_ids(chapter_id="chapter:1"), {"section:1", "section:2"})

    def test_graph_queries_relationships(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        self.assertEqual(graph.sections_teaching_concept("concept:unit"), ["section:1"])
        self.assertEqual(graph.prerequisite_sections("section:2"), ["section:1"])
        self.assertEqual(graph.required_concepts_for_section("section:2"), ["concept:unit"])
        self.assertEqual(graph.weak_area_remediation_sections(["concept:unit"]), ["section:1"])

    def test_search_sections_uses_summaries(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        results = graph.search_sections("SI")
        self.assertEqual(results[0]["section_id"], "section:2")


if __name__ == "__main__":
    unittest.main()
