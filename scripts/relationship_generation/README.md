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
export GEMINI_MODEL="gemini-3.5-flash"
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
# Generate section summaries for every chapter in the cleaned corpus. This stage
# does not require canonical concepts.
python3 scripts/relationship_generation/03_generate_section_summaries.py \
  --force

python3 scripts/relationship_generation/01_extract_chapter_concepts.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/02_normalize_concepts.py \
  --use-gemini-adjudication

python3 scripts/relationship_generation/03_generate_section_summaries.py \
  --chapter-id ncert:physics:11:1

python3 scripts/relationship_generation/04_generate_section_relationships.py \
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
- `section_summaries.jsonl`
- `raw_section_concept_relationships.jsonl`
- `raw_section_dependency_relationships.jsonl`
- `section_relationship_runs.jsonl`
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

Same-unit `TEACHES_CONCEPT` and `REQUIRES_CONCEPT` conflicts are sent to review.

## Relationship Types

- `DEPENDS_ON_UNIT`: unit should be learned after another unit in the same chapter.
- `REQUIRES_CONCEPT`: unit expects prior mastery of a concept.
- `TEACHES_CONCEPT`: unit teaches or reinforces a concept.

Every generated relationship must include evidence text, a reason, and confidence.

## Source Structure Note

The cleaned JSON uses `chapter.sections[]` as a flattened heading/unit layer.
Those section IDs may look like `1`, `1.2`, `1.2.1`, or `Summary`. Each section
row owns its atomic prose chunks in `section.subsections[]`. The section-summary
stage writes one summary per `chapter.sections[]` row, not one summary per
`section.subsections[]` row.
