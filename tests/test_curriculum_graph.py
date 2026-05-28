from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from curriculum_engine import (
    ArtifactStore,
    CurriculumGraph,
    CurriculumRetriever,
    LearnerConceptState,
    LearnerConceptStatus,
    TextbookStore,
)


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
                    },
                    {
                        "id": "chapter:2",
                        "subject": "physics",
                        "grade": 11,
                        "chapter_number": 2,
                        "chapter_title": "Motion",
                        "path": "data/textbook_sources/physics/grade_11/ch2.json",
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
                        {"id": "section:Summary", "number": None, "title": "Summary", "content_text": "", "subsections": []},
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_json(
            self.root / "data/textbook_sources/physics/grade_11/ch2.json",
            {
                "id": "chapter:2",
                "subject": "physics",
                "grade": 11,
                "chapter": {
                    "id": "chapter:2",
                    "title": "Motion",
                    "sections": [
                        {"id": "section:4", "number": "2.1", "title": "Speed", "content_text": "", "subsections": []},
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
                {"chapter_id": "chapter:1", "section_id": "section:3", "title": "Dimensional Analysis", "summary": "Uses dimensions to test equations.", "key_terms": ["dimension"]},
                {"chapter_id": "chapter:1", "section_id": "section:Summary", "title": "Summary", "summary": "Recap.", "key_terms": ["summary"]},
                {"chapter_id": "chapter:2", "section_id": "section:4", "title": "Speed", "summary": "Defines speed.", "key_terms": ["speed"]},
            ],
        )
        write_json(
            self.root / "data/relationship_artifacts/usable_chapters.json",
            {
                "status": "ok",
                "usable_chapter_ids": ["chapter:1"],
            },
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [
                {"concept_id": "concept:unit", "canonical_label": "Unit", "normalized_label": "unit", "aliases": []},
                {"concept_id": "concept:si_units", "canonical_label": "SI Units", "normalized_label": "si_units", "aliases": ["International System of Units"]},
                {"concept_id": "concept:dimensional_analysis", "canonical_label": "Dimensional Analysis", "normalized_label": "dimensional_analysis", "aliases": []},
                {"concept_id": "concept:universal_law_of_gravitation", "canonical_label": "Universal Law of Gravitation", "normalized_label": "universal_law_of_gravitation", "aliases": []},
                {"concept_id": "concept:myasthenia_gravis", "canonical_label": "Myasthenia gravis", "normalized_label": "myasthenia_gravis", "aliases": []},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:1", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:2", "to_id": "concept:si_units"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:3", "to_id": "concept:dimensional_analysis"},
                {"chapter_id": "chapter:1", "type": "DEPENDS_ON_UNIT", "from_id": "section:2", "to_id": "section:1"},
                {"chapter_id": "chapter:1", "type": "DEPENDS_ON_UNIT", "from_id": "section:3", "to_id": "section:1"},
                {"chapter_id": "chapter:1", "type": "REQUIRES_CONCEPT", "from_id": "section:2", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "REQUIRES_CONCEPT", "from_id": "section:3", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "TRANSFER_SUPPORTS_UNIT", "from_id": "section:3", "to_id": "section:2"},
                {"chapter_id": "chapter:1", "type": "RELATED_BY_CONCEPT", "from_id": "section:2", "to_id": "section:3"},
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_textbook_store_loads_section_ids(self) -> None:
        store = TextbookStore(self.root)
        self.assertEqual(store.section_ids(chapter_id="chapter:1"), {"section:1", "section:2", "section:3"})

    def test_graph_queries_relationships(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        self.assertEqual(graph.sections_teaching_concept("concept:unit"), ["section:1"])
        self.assertEqual(graph.prerequisite_sections("section:2"), ["section:1"])
        self.assertEqual(graph.dependents_of_section("section:1"), ["section:2", "section:3"])
        self.assertEqual(graph.required_concepts_for_section("section:2"), ["concept:unit"])
        self.assertEqual(graph.transfer_support_sections("section:3"), ["section:2"])
        self.assertEqual(graph.transfer_source_sections("section:2"), ["section:3"])
        self.assertEqual(graph.related_sections_by_concept("section:2"), ["section:3"])
        self.assertEqual(graph.weak_area_remediation_sections(["concept:unit"]), ["section:1"])
        self.assertEqual(graph.teaches_concept_details("section:2")[0]["label"], "SI Units")
        self.assertEqual(graph.requires_concept_details("section:2")[0]["label"], "Unit")
        self.assertEqual(graph.hard_dependency_edges_for_section("section:2")[0]["to_section_id"], "section:1")

    def test_graph_uses_cached_indexes(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        self.assertIs(graph.relationships_by_type_index, graph.relationships_by_type_index)
        self.assertEqual(graph.taught_concepts_by_section["section:2"], ["concept:si_units"])
        self.assertEqual(graph.required_concepts_by_section["section:3"], ["concept:unit"])
        self.assertEqual(graph.concept_ids_for_query("International System of Units"), ["concept:si_units"])
        self.assertIn("concept:universal_law_of_gravitation", graph.concept_ids_for_query("gravitation"))
        self.assertNotIn("concept:myasthenia_gravis", graph.concept_ids_for_query("gravitation"))
        self.assertNotIn("concept:universal_law_of_gravitation", graph.concept_ids_for_query("law"))

    def test_graph_expands_concepts_and_prerequisites(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        self.assertEqual(graph.teaching_sections_for_concepts(["concept:si_units", "concept:unit"]), ["section:2", "section:1"])
        self.assertEqual(graph.prerequisite_concepts_for_sections(["section:2", "section:3"]), ["concept:unit"])
        self.assertEqual(graph.prerequisite_sections_for_sections(["section:2", "section:3"]), ["section:1"])

    def test_search_sections_uses_summaries(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        results = graph.search_sections("SI")
        self.assertEqual(results[0]["section_id"], "section:2")

    def test_graph_can_filter_to_usable_chapters(self) -> None:
        graph = CurriculumGraph.from_repo(self.root, usable_only=True)

        self.assertEqual(graph.usable_chapter_ids, {"chapter:1"})
        self.assertIn("section:1", graph.sections_by_id)
        self.assertNotIn("section:4", graph.sections_by_id)
        self.assertEqual([row["section_id"] for row in graph.search_sections("speed")], [])

    def test_artifact_store_exposes_usable_summaries(self) -> None:
        store = ArtifactStore(self.root)

        self.assertEqual(store.usable_chapter_ids(), {"chapter:1"})
        self.assertEqual(
            {row["section_id"] for row in store.section_summaries_for_usable_chapters()},
            {"section:1", "section:2", "section:3"},
        )

    def test_retriever_finds_concept_label_and_prerequisites(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        results = CurriculumRetriever(graph).search("SI Units", include_prerequisites=True)
        self.assertEqual(results[0].section_id, "section:2")
        self.assertIn("concept:si_units", results[0].matched_concept_ids)
        self.assertTrue(any(result.section_id == "section:1" and "prerequisite" in result.reasons for result in results))

    def test_retriever_filters_by_subject_grade_and_chapter(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        retriever = CurriculumRetriever(graph)
        self.assertEqual([r.section_id for r in retriever.search("unit", subject="physics", grade=11, chapter_id="chapter:1")], ["section:1"])
        self.assertEqual(retriever.search("unit", subject="chemistry"), [])
        self.assertEqual(retriever.search("unit", grade=12), [])

    def test_subject_filter_applies_to_seed_matching_but_not_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "data/textbook_sources/manifest.json",
                {
                    "chapters": [
                        {
                            "id": "chem:1",
                            "subject": "chemistry",
                            "grade": 11,
                            "chapter_number": 1,
                            "chapter_title": "Catalysis",
                            "path": "data/textbook_sources/chemistry/grade_11/ch1.json",
                        },
                        {
                            "id": "phys:1",
                            "subject": "physics",
                            "grade": 11,
                            "chapter_number": 1,
                            "chapter_title": "Energy",
                            "path": "data/textbook_sources/physics/grade_11/ch1.json",
                        },
                    ]
                },
            )
            write_json(
                root / "data/textbook_sources/chemistry/grade_11/ch1.json",
                {
                    "id": "chem:1",
                    "subject": "chemistry",
                    "grade": 11,
                    "chapter": {
                        "id": "chem:1",
                        "title": "Catalysis",
                        "sections": [
                            {"id": "chem:section", "number": "1.1", "title": "Catalyst Action", "content_text": "", "subsections": []},
                        ],
                        "exercises": {"items": []},
                    },
                },
            )
            write_json(
                root / "data/textbook_sources/physics/grade_11/ch1.json",
                {
                    "id": "phys:1",
                    "subject": "physics",
                    "grade": 11,
                    "chapter": {
                        "id": "phys:1",
                        "title": "Energy",
                        "sections": [
                            {"id": "phys:section", "number": "1.1", "title": "Energy Barrier", "content_text": "", "subsections": []},
                        ],
                        "exercises": {"items": []},
                    },
                },
            )
            write_json(root / "data/relationship_artifacts/usable_chapters.json", {"usable_chapter_ids": ["chem:1", "phys:1"]})
            write_jsonl(
                root / "data/relationship_artifacts/section_summaries.jsonl",
                [
                    {"chapter_id": "chem:1", "section_id": "chem:section", "title": "Catalyst Action", "summary": "Catalyst action in chemical reactions.", "key_terms": ["catalyst"]},
                    {"chapter_id": "phys:1", "section_id": "phys:section", "title": "Energy Barrier", "summary": "Energy barrier needed before reactions proceed.", "key_terms": ["energy"]},
                ],
            )
            write_jsonl(
                root / "data/relationship_artifacts/canonical_concepts.jsonl",
                [
                    {"concept_id": "concept:catalyst", "canonical_label": "Catalyst", "normalized_label": "catalyst", "aliases": []},
                    {"concept_id": "concept:energy_barrier", "canonical_label": "Energy Barrier", "normalized_label": "energy_barrier", "aliases": []},
                ],
            )
            write_jsonl(
                root / "data/relationship_artifacts/accepted_relationships.jsonl",
                [
                    {"chapter_id": "chem:1", "type": "TEACHES_CONCEPT", "from_id": "chem:section", "to_id": "concept:catalyst"},
                    {"chapter_id": "phys:1", "type": "TEACHES_CONCEPT", "from_id": "phys:section", "to_id": "concept:energy_barrier"},
                    {"chapter_id": "chem:1", "type": "DEPENDS_ON_UNIT", "from_id": "chem:section", "to_id": "phys:section"},
                ],
            )

            graph = CurriculumGraph(TextbookStore(root), ArtifactStore(root), usable_only=True)
            results = CurriculumRetriever(graph).search("catalyst", subject="chemistry", include_prerequisites=True)
            by_id = {result.section_id: result for result in results}

            self.assertIn("chem:section", by_id)
            self.assertIn("phys:section", by_id)
            self.assertIn("prerequisite", by_id["phys:section"].reasons)

    def test_retriever_personalization_boosts_misconceptions(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        retriever = CurriculumRetriever(graph)
        baseline = retriever.search("dimension", include_prerequisites=False)
        boosted = retriever.search(
            "dimension",
            learner_state=[
                LearnerConceptState(
                    concept_id="concept:dimensional_analysis",
                    status=LearnerConceptStatus.MISCONCEPTION,
                    confidence=1.0,
                    recency_weight=1.0,
                )
            ],
            include_prerequisites=False,
        )
        self.assertGreater(boosted[0].score, baseline[0].score)
        self.assertIn("learner_misconception", boosted[0].reasons)

    def test_retriever_competency_lowers_but_keeps_results(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        retriever = CurriculumRetriever(graph)
        baseline = retriever.search("SI Units", include_prerequisites=False)
        lowered = retriever.search(
            "SI Units",
            learner_state=[
                LearnerConceptState(
                    concept_id="concept:si_units",
                    status=LearnerConceptStatus.COMPETENT,
                    confidence=1.0,
                    recency_weight=1.0,
                )
            ],
            include_prerequisites=False,
        )
        self.assertEqual(lowered[0].section_id, "section:2")
        self.assertLess(lowered[0].score, baseline[0].score)
        self.assertIn("learner_competency", lowered[0].reasons)

    def test_retriever_ordering_is_deterministic_for_ties(self) -> None:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        results = CurriculumRetriever(graph).search("units", include_prerequisites=False)
        self.assertEqual([result.section_id for result in results[:2]], ["section:1", "section:2"])


if __name__ == "__main__":
    unittest.main()
