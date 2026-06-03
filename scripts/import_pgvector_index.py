"""Import the prebuilt section vector index into Postgres/pgvector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from curriculum_engine.database import PostgresRepository, database_url, run_schema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--skip-schema", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    url = args.database_url or database_url()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    if not args.skip_schema:
        run_schema(url, schema_path=root / "database/schema.sql")

    docs_path = root / "data/retrieval_index/section_documents.jsonl"
    vectors_path = root / "data/retrieval_index/section_vectors.npy"
    if not docs_path.exists() or not vectors_path.exists():
        raise SystemExit("Missing data/retrieval_index artifacts")

    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit("numpy is required to import vectors") from exc

    documents = [json.loads(line) for line in docs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    vectors = np.load(vectors_path)
    if len(documents) != len(vectors):
        raise SystemExit(f"Document/vector mismatch: {len(documents)} docs, {len(vectors)} vectors")
    if vectors.ndim != 2 or vectors.shape[1] != 1024:
        raise SystemExit(f"Expected vectors with dimension 1024, got shape {vectors.shape}")

    repo = PostgresRepository(url)
    with repo._connect() as conn:
        with conn.cursor() as cur:
            for doc, vector in zip(documents, vectors, strict=True):
                cur.execute(
                    """
                    insert into section_embedding_documents(
                      section_id, chapter_id, subject, grade, title, embedding_text,
                      taught_concept_ids, required_concept_ids, embedding, updated_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::vector, now())
                    on conflict (section_id) do update set
                      chapter_id = excluded.chapter_id,
                      subject = excluded.subject,
                      grade = excluded.grade,
                      title = excluded.title,
                      embedding_text = excluded.embedding_text,
                      taught_concept_ids = excluded.taught_concept_ids,
                      required_concept_ids = excluded.required_concept_ids,
                      embedding = excluded.embedding,
                      updated_at = now()
                    """,
                    (
                        doc["section_id"],
                        doc["chapter_id"],
                        doc.get("subject"),
                        doc.get("grade"),
                        doc.get("title") or "",
                        doc.get("text") or "",
                        json.dumps(doc.get("taught_concept_ids") or []),
                        json.dumps(doc.get("required_concept_ids") or []),
                        "[" + ",".join(f"{float(value):.9g}" for value in vector) + "]",
                    ),
                )

    health = repo.health()
    print(json.dumps({"imported": len(documents), **health}, indent=2))


if __name__ == "__main__":
    main()
