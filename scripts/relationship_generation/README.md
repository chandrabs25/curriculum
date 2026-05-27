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
# Generate section summaries and raw concept candidates for every chapter in the
# cleaned corpus. This stage does not require canonical concepts.
python3 scripts/relationship_generation/03_generate_section_summaries.py \
  --force

python3 scripts/relationship_generation/02_normalize_concepts.py \
  --use-gemini-adjudication

python3 scripts/relationship_generation/07_gate_relationships.py --force

python3 scripts/relationship_generation/08_validate_artifacts.py

# If extraction stops early, build an index of chapters that are safe to use
# without spending more API calls.
python3 scripts/relationship_generation/11_build_usable_corpus.py

# Build deterministic concept links, hard prerequisites, and soft cross-chapter
# bridges from the raw concepts we already extracted, then gate them into
# accepted relationships.
python3 scripts/relationship_generation/12_build_section_concept_links.py \
  --force

python3 scripts/relationship_generation/07_gate_relationships.py \
  --force

python3 scripts/relationship_generation/08_validate_artifacts.py \
  --usable-only
```

If you do not activate the virtualenv, call the scripts with:

```bash
.venv/bin/python scripts/relationship_generation/03_generate_section_summaries.py \
  --chapter-id ncert:physics:11:1
```

Then run the full corpus by omitting `--chapter-id`.

## Artifacts

Main outputs are written to `data/relationship_artifacts/`:

- `raw_concepts.jsonl`
- `canonical_concepts.jsonl`
- `concept_aliases.jsonl`
- `section_summaries.jsonl`
- `accepted_relationships.jsonl`
- `relationship_summary.json`
- `validation_report.json`
- `usable_chapters.json`
- `section_concept_index.json`

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

- `DEPENDS_ON_UNIT`: hard same-chapter prerequisite; unit should be learned after another unit.
- `RELATED_BY_CONCEPT`: soft section bridge; two sections teach the same concept.
- `REQUIRES_CONCEPT`: unit expects prior mastery of a concept.
- `TEACHES_CONCEPT`: unit teaches or reinforces a concept.
- `TRANSFER_SUPPORTS_UNIT`: soft cross-chapter bridge; one section teaches a concept required by another section.

Every generated relationship must include evidence text, a reason, and confidence.

## Partial Corpus Mode

If Gemini quota runs out before all section summaries are generated, run:

```bash
python3 scripts/relationship_generation/11_build_usable_corpus.py
```

This writes `usable_chapters.json`, which marks only fully covered chapters as
usable. Application code can load `CurriculumGraph.from_repo(...,
usable_only=True)` to restrict retrieval/planning to those completed chapters.

Without additional Gemini calls, you can still build concept and dependency graph
links:

```bash
python3 scripts/relationship_generation/12_build_section_concept_links.py --force
python3 scripts/relationship_generation/07_gate_relationships.py --force
python3 scripts/relationship_generation/08_validate_artifacts.py --usable-only
```

This creates `TEACHES_CONCEPT` and `REQUIRES_CONCEPT` relationships from
extracted raw concepts, infers same-chapter `DEPENDS_ON_UNIT` candidates where a
required concept is taught by another section, adds cross-chapter
`TRANSFER_SUPPORTS_UNIT` and `RELATED_BY_CONCEPT` bridges, and writes
`section_concept_index.json`.

## Source Structure Note

The cleaned JSON uses `chapter.sections[]` as a flattened heading/unit layer.
Those section IDs may look like `1`, `1.2`, `1.2.1`, or `Summary`. Each section
row owns its atomic prose chunks in `section.subsections[]`. The section-summary
stage writes one summary plus raw concept candidates per `chapter.sections[]`
row, not one summary per `section.subsections[]` row.

Application-facing curriculum and graph stages only use numbered section IDs
whose final ID segment matches `1`, `1.2`, or `1.2.1`. Non-curriculum section
IDs such as `Summary`, `Answers`, `Exercises`, `Appendix`, and
`Points to Ponder` are excluded from usable corpus indexing, relationship
generation, validation, and graph retrieval.
