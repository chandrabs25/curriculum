from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from curriculum_engine import (
    ArtifactStore,
    ArtifactValidationError,
    RawConceptArtifact,
    RawConceptRelationshipType,
    RelationshipType,
    SectionSummaryArtifact,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class ArtifactContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact_root = self.root / "data/relationship_artifacts"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_section_summary_contract(self) -> None:
        row = {
            "section_summary_id": "section_summary:1",
            "chapter_id": "chapter:1",
            "section_id": "section:1",
            "section_number": "1.1",
            "title": "Units",
            "summary": "Defines measurement units.",
            "key_terms": ["unit"],
            "covered_subsection_ids": ["section:1:1"],
            "evidence_snippets": [{"text": "A unit is a standard."}],
            "confidence": 0.9,
            "generation": {"model": "gemini-3.5-flash"},
        }

        artifact = SectionSummaryArtifact.from_row(row)

        self.assertEqual(artifact.section_id, "section:1")
        self.assertEqual(artifact.key_terms, ["unit"])
        self.assertEqual(artifact.confidence, 0.9)

    def test_typed_artifact_store_loads_contracts(self) -> None:
        write_jsonl(
            self.artifact_root / "section_summaries.jsonl",
            [
                {
                    "section_summary_id": "section_summary:1",
                    "chapter_id": "chapter:1",
                    "section_id": "section:1",
                    "title": "Units",
                    "summary": "Defines units.",
                    "key_terms": ["unit"],
                    "covered_subsection_ids": [],
                    "evidence_snippets": [{"text": "A unit is a standard."}],
                    "confidence": 1.0,
                }
            ],
        )
        write_jsonl(
            self.artifact_root / "raw_concepts.jsonl",
            [
                {
                    "raw_concept_id": "raw_concept:1",
                    "chapter_id": "chapter:1",
                    "subject": "physics",
                    "grade": 11,
                    "chapter_title": "Measurement",
                    "source_section_id": "section:1",
                    "relationship_type": "teaches",
                    "label": "Unit",
                    "normalized_label": "unit",
                    "candidate_concept_id": "concept:unit",
                    "definition": "A measurement standard.",
                    "source_unit_ids": ["section:1"],
                    "evidence": [{"unit_id": "section:1", "text": "A unit is a standard."}],
                    "confidence": 0.95,
                },
                {
                    "raw_concept_id": "raw_concept:2",
                    "chapter_id": "chapter:1",
                    "source_section_id": "section:2",
                    "relationship_type": "requires",
                    "label": "Unit",
                    "normalized_label": "unit",
                    "candidate_concept_id": "concept:unit",
                    "reason": "The section assumes measurements with units.",
                    "source_unit_ids": ["section:2"],
                    "evidence": [{"unit_id": "section:2", "text": "The section assumes measurements with units."}],
                    "confidence": 0.8,
                },
            ],
        )
        write_jsonl(
            self.artifact_root / "canonical_concepts.jsonl",
            [
                {
                    "concept_id": "concept:unit",
                    "canonical_label": "Unit",
                    "normalized_label": "unit",
                    "definition": "A measurement standard.",
                    "aliases": [],
                    "source_raw_concept_ids": ["raw_concept:1", "raw_concept:2"],
                    "source_chapter_ids": ["chapter:1"],
                    "source_unit_ids": ["section:1", "section:2"],
                    "subjects": ["physics"],
                    "confidence": 0.95,
                }
            ],
        )
        write_jsonl(
            self.artifact_root / "accepted_relationships.jsonl",
            [
                {
                    "relationship_id": "rel:1",
                    "chapter_id": "chapter:1",
                    "type": "TEACHES_CONCEPT",
                    "from_id": "section:1",
                    "to_id": "concept:unit",
                    "confidence": 0.95,
                    "evidence": {"unit_id": "section:1", "text": "A unit is a standard.", "reason": "Definition."},
                    "generation": {"script": "07_gate_relationships.py"},
                    "gate_reasons": [],
                }
            ],
        )

        store = ArtifactStore(self.root)

        self.assertEqual(store.typed_section_summaries()[0].section_id, "section:1")
        self.assertEqual(store.typed_raw_concepts()[0].relationship_type, RawConceptRelationshipType.TEACHES)
        self.assertEqual(store.typed_raw_concepts()[1].relationship_type, RawConceptRelationshipType.REQUIRES)
        self.assertEqual(store.typed_concepts()[0].concept_id, "concept:unit")
        self.assertEqual(store.typed_relationships()[0].type, RelationshipType.TEACHES_CONCEPT)

    def test_contract_rejects_invalid_relationship_type(self) -> None:
        row = {
            "raw_concept_id": "raw_concept:1",
            "chapter_id": "chapter:1",
            "source_section_id": "section:1",
            "relationship_type": "unknown",
            "label": "Unit",
            "normalized_label": "unit",
            "candidate_concept_id": "concept:unit",
            "source_unit_ids": ["section:1"],
            "evidence": [{"unit_id": "section:1", "text": "A unit is a standard."}],
            "confidence": 0.9,
        }

        with self.assertRaises(ArtifactValidationError):
            RawConceptArtifact.from_row(row)


if __name__ == "__main__":
    unittest.main()
