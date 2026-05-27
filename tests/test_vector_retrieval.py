from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from curriculum_engine import (
    ArtifactStore,
    CurriculumGraph,
    CurriculumRetriever,
    TextbookStore,
    VectorSearchResult,
    build_section_documents,
)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeVectorIndex:
    def __init__(self, results: list[VectorSearchResult]):
        self.results = results

    def search(self, query: str, *, limit: int = 20) -> list[VectorSearchResult]:
        return self.results[:limit]


class VectorRetrievalTest(unittest.TestCase):
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
                        {"id": "section:3", "number": "1.3", "title": "Dimensional Analysis", "content_text": "", "subsections": []},
                        {"id": "section:4", "number": "1.4", "title": "Measurement Practice", "content_text": "", "subsections": []},
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
                {"chapter_id": "chapter:1", "section_id": "section:2:1", "title": "SI base units detail", "summary": "Detailed subsection about base SI units.", "key_terms": ["SI", "base"]},
                {"chapter_id": "chapter:1", "section_id": "section:3", "title": "Dimensional Analysis", "summary": "Checks equations.", "key_terms": ["dimension"]},
                {"chapter_id": "chapter:1", "section_id": "section:4", "title": "Measurement Practice", "summary": "Practice with units.", "key_terms": ["practice"]},
                {"chapter_id": "chapter:1", "section_id": "section:5", "title": "Points to Ponder", "summary": "Meta review points about units.", "key_terms": ["unit"]},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [
                {"concept_id": "concept:unit", "canonical_label": "Unit", "normalized_label": "unit", "aliases": [], "confidence": 1.0},
                {"concept_id": "concept:si_units", "canonical_label": "SI Units", "normalized_label": "si_units", "aliases": [], "confidence": 1.0},
                {"concept_id": "concept:dimensional_analysis", "canonical_label": "Dimensional Analysis", "normalized_label": "dimensional_analysis", "aliases": [], "confidence": 1.0},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:1", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:2", "to_id": "concept:si_units"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:3", "to_id": "concept:dimensional_analysis"},
                {"chapter_id": "chapter:1", "type": "REQUIRES_CONCEPT", "from_id": "section:2", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "DEPENDS_ON_UNIT", "from_id": "section:2", "to_id": "section:1"},
                {"chapter_id": "chapter:1", "type": "TRANSFER_SUPPORTS_UNIT", "from_id": "section:3", "to_id": "section:2"},
                {"chapter_id": "chapter:1", "type": "RELATED_BY_CONCEPT", "from_id": "section:2", "to_id": "section:4"},
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def graph(self) -> CurriculumGraph:
        return CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))

    def test_section_documents_include_concept_labels(self) -> None:
        docs = {doc.section_id: doc for doc in build_section_documents(self.graph())}

        self.assertIn("SI Units", docs["section:2"].text)
        self.assertIn("concept:si_units", docs["section:2"].text)
        self.assertIn("Requires concepts: concept:unit", docs["section:2"].text)

    def test_vector_matches_are_used_with_prerequisites_and_soft_links(self) -> None:
        graph = self.graph()
        retriever = CurriculumRetriever(
            graph,
            vector_index=FakeVectorIndex([VectorSearchResult("section:2", 0.9)]),
        )

        results = retriever.search("international units", limit=4)
        by_id = {row.section_id: row for row in results}

        self.assertEqual(results[0].section_id, "section:2")
        self.assertIn("vector_match", by_id["section:2"].reasons)
        self.assertIn("section:1", by_id)
        self.assertIn("prerequisite", by_id["section:1"].reasons)
        self.assertIn("section:3", by_id)
        self.assertIn("transfer_support", by_id["section:3"].reasons)
        self.assertIn("section:4", by_id)
        self.assertIn("related_concept", by_id["section:4"].reasons)

    def test_vector_match_can_include_subsection_but_lexical_cannot(self) -> None:
        graph = self.graph()

        lexical_results = CurriculumRetriever(graph).search("base SI units", limit=5, include_prerequisites=False, include_soft_links=False)
        self.assertNotIn("section:2:1", {row.section_id for row in lexical_results})

        vector_results = CurriculumRetriever(
            graph,
            vector_index=FakeVectorIndex([VectorSearchResult("section:2:1", 0.9)]),
        ).search("base SI units", limit=5, include_prerequisites=False, include_soft_links=False)
        by_id = {row.section_id: row for row in vector_results}
        self.assertIn("section:2:1", by_id)
        self.assertIn("vector_match", by_id["section:2:1"].reasons)

    def test_meta_sections_are_excluded(self) -> None:
        results = CurriculumRetriever(self.graph()).search("ponder units", limit=5, include_prerequisites=False, include_soft_links=False)

        self.assertNotIn("section:5", {row.section_id for row in results})

    def test_retriever_falls_back_without_vector_index(self) -> None:
        results = CurriculumRetriever(self.graph()).search("SI Units", limit=2)

        self.assertEqual(results[0].section_id, "section:2")
        self.assertNotIn("vector_match", results[0].reasons)


if __name__ == "__main__":
    unittest.main()
