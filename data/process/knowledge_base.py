"""Index the Nexova commercial knowledge base in Qdrant."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models


COLLECTION_NAME = "nexova_knowledge"
DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SOURCE_DOCUMENTS = (
    ("service-lines", "nexova-service-lines.es.md"),
    ("pricing-model", "nexova-pricing-model.es.md"),
    ("hiring-process-sla", "nexova-hiring-process-sla.es.md"),
    ("objection-handling", "nexova-objection-handling.es.md"),
)
CORPUS_DIR = Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"
MAX_CHUNK_CHARS = 1200
CHUNK_NAMESPACE = uuid.UUID("7a505623-326a-4e36-b7ea-4cb3b10d7536")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
NUMBERED_ITEM_PATTERN = re.compile(r"^\s{0,3}\d+[.)]\s+")
QUOTED_ITEM_PATTERN = re.compile(r"^\s*[\"“]")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _embedding_dimension() -> int:
    try:
        dimension = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    except ValueError:
        raise ValueError("EMBEDDING_DIMENSION debe ser un entero positivo.") from None
    if dimension <= 0:
        raise ValueError("EMBEDDING_DIMENSION debe ser un entero positivo.")
    return dimension


@lru_cache(maxsize=2)
def _embedding_model(model_name: str) -> Any:
    try:
        from fastembed import TextEmbedding

        return TextEmbedding(model_name=model_name)
    except Exception:
        raise RuntimeError(
            f"No se pudo cargar el modelo de embeddings '{model_name}'. "
            "Comprueba que EMBED_MODEL sea un modelo FastEmbed válido y que esté disponible."
        ) from None


def embed(text: str) -> list[float]:
    """Create the configured FastEmbed vector used for indexing and retrieval."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("El texto para generar el embedding no puede estar vacío.")

    model_name = os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL)
    try:
        vector = next(_embedding_model(model_name).embed([text]))
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        values = [float(value) for value in values]
    except Exception:
        raise RuntimeError(
            f"No se pudo generar el embedding con '{model_name}'. "
            "Comprueba la disponibilidad local del modelo y vuelve a intentarlo."
        ) from None

    expected_dimension = _embedding_dimension()
    if len(values) != expected_dimension:
        raise ValueError(
            f"El modelo '{model_name}' devolvió {len(values)} dimensiones; "
            f"EMBEDDING_DIMENSION está configurado en {expected_dimension}."
        )
    return values


def _semantic_blocks(markdown: str) -> list[tuple[str, str]]:
    section = "General"
    block_lines: list[str] = []
    blocks: list[tuple[str, str]] = []

    def flush() -> None:
        text = "\n".join(block_lines).strip()
        if text:
            blocks.append((section, text))
        block_lines.clear()

    for line in markdown.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            flush()
            section = heading.group(1).strip()
            continue
        if not line.strip():
            flush()
            continue
        if block_lines and (
            NUMBERED_ITEM_PATTERN.match(line) or QUOTED_ITEM_PATTERN.match(line)
        ):
            flush()
        block_lines.append(line.rstrip())

    flush()
    return blocks


def _split_oversized_block(section: str, text: str, max_chars: int) -> list[tuple[str, str]]:
    if len(text) <= max_chars:
        return [(section, text)]

    sentences = SENTENCE_PATTERN.split(text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [(section, chunk) for chunk in chunks]


def chunk_markdown(markdown: str, max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[str, str]]:
    """Split a Markdown document on headings and complete semantic blocks."""
    if max_chars <= 0:
        raise ValueError("max_chars debe ser mayor que cero.")
    chunks = [
        chunk
        for section, text in _semantic_blocks(markdown)
        for chunk in _split_oversized_block(section, text, max_chars)
    ]
    if len(chunks) < 3:
        raise ValueError(
            f"El documento produjo {len(chunks)} chunks; se requieren al menos 3. "
            "Añade estructura semántica al documento o ajusta el chunking."
        )
    return chunks


def _point_id(source_document: str, section: str, chunk_index: int, text: str) -> str:
    normalized_text = " ".join(text.split())
    identity = f"{source_document}\0{section}\0{chunk_index}\0{normalized_text}"
    return str(uuid.uuid5(CHUNK_NAMESPACE, identity))


def _source_filter(source_document: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="source_document",
                match=models.MatchValue(value=source_document),
            )
        ]
    )


def _existing_source_ids(client: QdrantClient, source_document: str) -> set[str]:
    point_ids: set[str] = set()
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=_source_filter(source_document),
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        point_ids.update(str(record.id) for record in records)
        if offset is None:
            return point_ids


def _ensure_collection(client: QdrantClient, dimension: int) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        try:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
        except Exception:
            raise RuntimeError(
                f"No se pudo crear la colección '{COLLECTION_NAME}'. "
                "Comprueba QDRANT_URL y los permisos del servicio."
            ) from None
        return

    try:
        collection = client.get_collection(COLLECTION_NAME)
        vector_config = collection.config.params.vectors
    except Exception:
        raise RuntimeError(
            f"No se pudo inspeccionar la colección '{COLLECTION_NAME}'. "
            "Comprueba que Qdrant esté disponible."
        ) from None

    if isinstance(vector_config, dict):
        raise RuntimeError(
            f"La colección '{COLLECTION_NAME}' usa vectores nombrados; "
            "se requiere una colección con un vector sin nombre."
        )
    if vector_config.size != dimension or vector_config.distance != models.Distance.COSINE:
        raise RuntimeError(
            f"La colección '{COLLECTION_NAME}' es incompatible: requiere dimensión "
            f"{dimension} y distancia Cosine, pero tiene dimensión {vector_config.size} "
            f"y distancia {vector_config.distance}. No se modificó la colección."
        )


def _read_corpus() -> list[tuple[str, str]]:
    documents = []
    for source_document, filename in SOURCE_DOCUMENTS:
        path = CORPUS_DIR / filename
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            raise FileNotFoundError(
                f"No se puede leer '{path}'. Comprueba el montaje de "
                "docs/company-knowledge-base en este entorno."
            ) from None
        documents.append((source_document, markdown))
    return documents


def _qdrant_client() -> QdrantClient:
    try:
        return QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "10")),
        )
    except Exception:
        raise RuntimeError(
            "No se pudo inicializar el cliente Qdrant. Comprueba QDRANT_URL."
        ) from None


def setup(client: QdrantClient | None = None) -> dict[str, int]:
    """Index all four source documents and remove stale points per source."""
    dimension = _embedding_dimension()
    qdrant = client or _qdrant_client()
    documents = _read_corpus()
    _ensure_collection(qdrant, dimension)

    counts: dict[str, int] = {}
    for source_document, markdown in documents:
        chunks = chunk_markdown(markdown)
        existing_ids = _existing_source_ids(qdrant, source_document)
        points = []
        for chunk_index, (section, text) in enumerate(chunks):
            point_id = _point_id(source_document, section, chunk_index, text)
            payload = {
                "company": "nexova",
                "source_document": source_document,
                "section": section,
                "language": "es",
                "chunk_index": chunk_index,
                "text": text,
            }
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embed(text),
                    payload=payload,
                )
            )

        try:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
            stale_ids = existing_ids - {str(point.id) for point in points}
            if stale_ids:
                qdrant.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=models.PointIdsList(points=sorted(stale_ids)),
                    wait=True,
                )
        except Exception:
            raise RuntimeError(
                f"No se pudo indexar '{source_document}' en Qdrant. "
                "Comprueba la conectividad y vuelve a ejecutar setup()."
            ) from None
        counts[source_document] = len(points)

    return counts