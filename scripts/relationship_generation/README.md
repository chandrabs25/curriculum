# Relationship Generation Pipeline

This pipeline turns content-only textbook source files in `data/textbook_sources/`
into auditable concept and relationship artifacts.

It does **not** reuse old LearnerOS `prerequisites` or exercise `tests` fields.
All relationships are generated from the cleaned textbook content.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export GEMINI_API_KEY="..."
```

Optional:

```bash
export GEMINI_MODEL="gemini-2.5-pro"
```

## Run Order

Start with one chapter:

```bash
python3 scripts/relationship_generation/run_pipeline.py \
  --chapter-id ncert:physics:11:1 \
  --force
```

Or run each stage manually:

```bash
python3 scripts/relationship_generation/01_extract_chapter_concepts.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/02_normalize_concepts.py \
  --use-gemini-adjudication

python3 scripts/relationship_generation/03_generate_unit_summaries.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/04_generate_unit_concept_edges.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/05_generate_unit_dependencies.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/06_generate_exercise_edges.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/07_gate_relationships.py --force

python3 scripts/relationship_generation/08_validate_artifacts.py
```

If you do not activate the virtualenv, call the scripts with:

```bash
.venv/bin/python scripts/relationship_generation/01_extract_chapter_concepts.py \
  --chapter-id ncert:physics:11:1
```

Then run the full corpus by omitting `--chapter-id`.

## Artifacts

Main outputs are written to `data/relationship_artifacts/`:

- `raw_concepts.jsonl`
- `canonical_concepts.jsonl`
- `concept_aliases.jsonl`
- `unit_summaries.jsonl`
- `raw_unit_concept_relationships.jsonl`
- `raw_unit_dependency_relationships.jsonl`
- `raw_exercise_relationships.jsonl`
- `accepted_relationships.jsonl`
- `relationship_summary.json`
- `validation_report.json`

Review queues:

- `review/concept_merges.jsonl`
- `review/relationships.jsonl`

Rejected records:

- `rejected/concepts.jsonl`
- `rejected/relationships.jsonl`

Errors:

- `errors.jsonl`

## Confidence Gate

Relationship gating defaults:

- `confidence >= 0.85`: accepted
- `0.65 <= confidence < 0.85`: review
- `< 0.65`: rejected

Records with dangling IDs, missing evidence, invalid relationship types, or duplicate
edges are rejected regardless of confidence.

## Relationship Types

- `DEPENDS_ON_UNIT`: unit should be learned after another unit in the same chapter.
- `REQUIRES_CONCEPT`: unit expects prior mastery of a concept.
- `TEACHES_CONCEPT`: unit teaches or reinforces a concept.
- `TESTS_UNIT`: exercise assesses a unit.
- `TESTS_CONCEPT`: exercise assesses a concept.

Every generated relationship must include evidence text, a reason, and confidence.
