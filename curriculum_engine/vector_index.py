"""Local vector retrieval over section-level curriculum documents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

from .graph import CurriculumGraph


DEFAULT_MODEL_DIR = Path(
    "/Users/srichandrasamanapalli/.cache/huggingface/hub/"
    "models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
)
DEFAULT_INDEX_DIR = Path("data/retrieval_index")


class EmbeddingModel(Protocol):
    def encode(self, texts: list[str]) -> Any:
        """Return a 2D array-like embedding matrix for texts."""


@dataclass(frozen=True)
class SectionDocument:
    section_id: str
    chapter_id: str
    subject: str | None
    grade: int | None
    title: str
    text: str
    taught_concept_ids: list[str]
    required_concept_ids: list[str]

    def to_row(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "chapter_id": self.chapter_id,
            "subject": self.subject,
            "grade": self.grade,
            "title": self.title,
            "text": self.text,
            "taught_concept_ids": self.taught_concept_ids,
            "required_concept_ids": self.required_concept_ids,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "SectionDocument":
        return cls(
            section_id=str(row["section_id"]),
            chapter_id=str(row["chapter_id"]),
            subject=row.get("subject"),
            grade=int(row["grade"]) if row.get("grade") is not None else None,
            title=str(row.get("title") or ""),
            text=str(row.get("text") or ""),
            taught_concept_ids=[str(item) for item in row.get("taught_concept_ids") or []],
            required_concept_ids=[str(item) for item in row.get("required_concept_ids") or []],
        )


@dataclass(frozen=True)
class VectorSearchResult:
    section_id: str
    score: float


class SentenceTransformerEmbeddingModel:
    def __init__(self, model_dir: Path | str = DEFAULT_MODEL_DIR):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for local BGE-M3 embeddings. "
                "Install requirements before building the retrieval index."
            ) from exc
        self.model_dir = Path(model_dir)
        self.model = SentenceTransformer(str(self.model_dir))

    def encode(self, texts: list[str]) -> Any:
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


@dataclass
class SectionVectorIndex:
    documents: list[SectionDocument]
    vectors: Any
    embedding_model: EmbeddingModel | None = None

    @classmethod
    def load(
        cls,
        root: Path | str = ".",
        *,
        index_dir: Path | str = DEFAULT_INDEX_DIR,
        embedding_model: EmbeddingModel | None = None,
    ) -> "SectionVectorIndex | None":
        root_path = Path(root)
        index_path = root_path / index_dir
        docs_path = index_path / "section_documents.jsonl"
        vectors_path = index_path / "section_vectors.npy"
        if not docs_path.exists() or not vectors_path.exists():
            return None
        try:
            import numpy as np
        except ImportError:
            return None
        documents = [SectionDocument.from_row(row) for row in _read_jsonl(docs_path)]
        vectors = np.load(vectors_path)
        if len(documents) != len(vectors):
            raise ValueError(
                f"retrieval index mismatch: {len(documents)} documents for {len(vectors)} vectors"
            )
        return cls(documents=documents, vectors=vectors, embedding_model=embedding_model)

    def with_embedding_model(self, embedding_model: EmbeddingModel) -> "SectionVectorIndex":
        self.embedding_model = embedding_model
        return self

    def search(self, query: str, *, limit: int = 20) -> list[VectorSearchResult]:
        if not self.embedding_model or not str(query or "").strip():
            return []
        try:
            import numpy as np
        except ImportError:
            return []
        query_vector = self.embedding_model.encode([query])
        query_array = np.asarray(query_vector, dtype="float32")
        if query_array.ndim != 2 or query_array.shape[0] != 1:
            raise ValueError("embedding model must return a single query vector")
        scores = np.dot(self.vectors, query_array[0])
        order = np.argsort(-scores)[:limit]
        return [
            VectorSearchResult(section_id=self.documents[int(idx)].section_id, score=float(scores[int(idx)]))
            for idx in order
            if float(scores[int(idx)]) > 0
        ]


def build_section_documents(graph: CurriculumGraph) -> list[SectionDocument]:
    documents = []
    for section_id, summary in sorted(graph.section_summaries_by_id.items()):
        section = graph.sections_by_id.get(section_id, {})
        taught = graph.concepts_taught_by_section(section_id)
        required = graph.required_concepts_for_section(section_id)
        documents.append(
            SectionDocument(
                section_id=section_id,
                chapter_id=str(summary.get("chapter_id") or section.get("chapter_id") or ""),
                subject=section.get("subject"),
                grade=section.get("grade"),
                title=str(summary.get("title") or section.get("title") or ""),
                text=section_embedding_text(graph, section_id, summary, section, taught, required),
                taught_concept_ids=taught,
                required_concept_ids=required,
            )
        )
    return documents


def section_embedding_text(
    graph: CurriculumGraph,
    section_id: str,
    summary: dict[str, Any],
    section: dict[str, Any],
    taught_concept_ids: list[str],
    required_concept_ids: list[str],
) -> str:
    taught_labels = _concept_labels(graph, taught_concept_ids)
    required_labels = _concept_labels(graph, required_concept_ids)
    parts = [
        f"Subject: {section.get('subject') or ''}",
        f"Grade: {section.get('grade') or ''}",
        f"Chapter: {summary.get('chapter_id') or section.get('chapter_id') or ''}",
        f"Section: {summary.get('title') or section.get('title') or section_id}",
        f"Summary: {summary.get('summary') or ''}",
        "Key terms: " + ", ".join(str(term) for term in summary.get("key_terms") or []),
        "Teaches concepts: " + ", ".join(taught_labels),
        "Requires concepts: " + ", ".join(required_labels),
    ]
    return "\n".join(part for part in parts if part.strip())


def write_vector_index(
    documents: list[SectionDocument],
    embedding_model: EmbeddingModel,
    *,
    output_dir: Path,
    model_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required to write the retrieval vector index") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    docs_path = output_dir / "section_documents.jsonl"
    vectors_path = output_dir / "section_vectors.npy"
    manifest_path = output_dir / "manifest.json"
    if not force and (docs_path.exists() or vectors_path.exists() or manifest_path.exists()):
        raise FileExistsError(f"{output_dir} already contains retrieval index files; use --force")

    vectors = np.asarray(embedding_model.encode([doc.text for doc in documents]), dtype="float32")
    _write_jsonl(docs_path, [doc.to_row() for doc in documents])
    np.save(vectors_path, vectors)
    manifest = {
        "index_type": "section_vector_index",
        "model_dir": str(model_dir),
        "document_count": len(documents),
        "embedding_dimension": int(vectors.shape[1]) if vectors.ndim == 2 else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _concept_labels(graph: CurriculumGraph, concept_ids: Iterable[str]) -> list[str]:
    labels = []
    for concept_id in concept_ids:
        concept = graph.concepts_by_id.get(concept_id, {})
        label = concept.get("canonical_label") or concept.get("normalized_label") or concept_id
        labels.append(f"{concept_id} ({label})")
    return labels


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
