import hashlib
import os
import re
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models


ROOT_DIR = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT_DIR / "docs" / "company-knowledge-base"
COLLECTION_NAME = "nexova_knowledge"
MAX_CHUNK_CHARS = 1800
#REQUEST_TIMEOUT = (5, 60)
REQUEST_TIMEOUT = (50, 200)
MAX_RETRIES = 5
BASE_RETRY_DELAY = 1.0  # seconds
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
SOURCE_DOCUMENTS = (
    ("service-lines", "nexova-service-lines.es.md"),
    ("pricing-model", "nexova-pricing-model.es.md"),
    ("hiring-process-sla", "nexova-hiring-process-sla.es.md"),
    ("objection-handling", "nexova-objection-handling.es.md"),
)


def _load_configuration() -> tuple[str, str, str | None]:
    load_dotenv(ROOT_DIR / ".env", override=False)
    model = os.getenv("EMBED_MODEL", "").strip()
    base_url = os.getenv("EMBED_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("EMBED_MODEL_API_KEY", "").strip()
    if not model:
        raise RuntimeError("EMBED_MODEL is required to create Nexova embeddings.")
    if not base_url:
        raise RuntimeError("EMBED_BASE_URL is required to create Nexova embeddings.")
    if not api_key:
        raise RuntimeError("EMBED_MODEL_API_KEY is required to create Nexova embeddings.")
    return model, base_url, os.getenv("EMBEDDING_DIMENSION")


def _embeddings_url(base_url: str) -> str:
    if base_url.endswith("/v1"):
        return f"{base_url}/embeddings"
    return f"{base_url}/v1/embeddings"


def embed(text: str) -> list[float]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding input must be a non-empty string.")

    model, base_url, configured_dimension = _load_configuration()
    api_key = os.getenv("EMBED_MODEL_API_KEY", "").strip()
    print(api_key)
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                _embeddings_url(base_url),
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "input": text},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(BASE_RETRY_DELAY * (2 ** attempt))
                continue
            raise RuntimeError("Embedding provider request failed; check endpoint connectivity.") from exc

        if response.status_code == 429 and attempt < MAX_RETRIES - 1:
            delay = BASE_RETRY_DELAY * (2 ** attempt)
            time.sleep(delay)
            continue

        break
    else:
        raise RuntimeError("Embedding provider request failed after max retries; check endpoint connectivity.") from last_exc

    if response.status_code in (401, 403):
        raise RuntimeError(
            f"Embedding provider rejected authentication (HTTP {response.status_code}); "
            "check EMBED_MODEL_API_KEY and provider access."
        )
    if not response.ok:
        raise RuntimeError(
            f"Embedding provider request failed (HTTP {response.status_code}); "
            "check EMBED_BASE_URL and EMBED_MODEL."
        )

    try:
        vector = response.json()["data"][0]["embedding"]
        vector = [float(value) for value in vector]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("Embedding provider returned an invalid vector response.") from exc

    if not vector or any(not (float("-inf") < value < float("inf")) for value in vector):
        raise RuntimeError("Embedding provider returned an empty or non-finite vector.")
    if configured_dimension:
        try:
            expected_dimension = int(configured_dimension)
        except ValueError as exc:
            raise RuntimeError("EMBEDDING_DIMENSION must be a positive integer.") from exc
        if expected_dimension <= 0 or len(vector) != expected_dimension:
            raise RuntimeError(
                "Embedding vector dimension does not match EMBEDDING_DIMENSION; "
                "verify the configured model and dimension."
            )
    return vector


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_oversized_block(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(markdown: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    section_titles: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        text = _normalize_text(" ".join(paragraph))
        paragraph.clear()
        if text:
            section = section_titles[-1] if section_titles else "General"
            chunks.extend((section, part) for part in _split_oversized_block(text))

    for line in markdown.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            section_titles[:] = section_titles[: level - 1]
            section_titles.append(heading.group(2).strip())
        elif line.strip():
            if LIST_ITEM_PATTERN.match(line) and any(
                LIST_ITEM_PATTERN.match(item) for item in paragraph
            ):
                flush_paragraph()
            paragraph.append(line.strip())
        else:
            flush_paragraph()
    flush_paragraph()
    return chunks


def _read_source_chunks() -> dict[str, list[tuple[int, str, str]]]:
    source_chunks: dict[str, list[tuple[int, str, str]]] = {}
    for source_document, filename in SOURCE_DOCUMENTS:
        path = CORPUS_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Knowledge source is missing: {path}")
        chunks = chunk_markdown(path.read_text(encoding="utf-8"))
        if len(chunks) < 3:
            raise RuntimeError(f"Knowledge source {filename} produced fewer than 3 chunks.")
        source_chunks[source_document] = [
            (index, section, text)
            for index, (section, text) in enumerate(chunks)
        ]
    return source_chunks


def _point_id(source_document: str, section: str, chunk_index: int, text: str) -> str:
    content = "\0".join(
        (source_document, _normalize_text(section), str(chunk_index), _normalize_text(text))
    )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))


def _scroll_source_points(client: QdrantClient, source_document: str):
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_document",
                        match=models.MatchValue(value=source_document),
                    )
                ]
            ),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        yield from points
        if offset is None:
            break


def _collection_vector_config(collection) -> tuple[int | None, models.Distance | None]:
    vectors = collection.config.params.vectors
    if isinstance(vectors, dict):
        if len(vectors) != 1:
            return None, None
        vectors = next(iter(vectors.values()))
    return vectors.size, vectors.distance


def setup(client: QdrantClient | None = None) -> dict[str, int]:
    if client is None:
        load_dotenv(ROOT_DIR / ".env", override=False)
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=10)

    source_chunks = _read_source_chunks()
    pending_points: dict[str, list[models.PointStruct]] = {}
    vector_dimension = None

    for source_document, chunks in source_chunks.items():
        points = []
        for chunk_index, section, text in chunks:
            vector = embed(text)
            if vector_dimension is None:
                vector_dimension = len(vector)
            elif len(vector) != vector_dimension:
                raise RuntimeError("Embedding provider returned inconsistent vector dimensions.")
            points.append(
                models.PointStruct(
                    id=_point_id(source_document, section, chunk_index, text),
                    vector=vector,
                    payload={
                        "company": "nexova",
                        "source_document": source_document,
                        "section": section,
                        "language": "es",
                        "chunk_index": chunk_index,
                        "text": text,
                    },
                )
            )
        pending_points[source_document] = points

    if not vector_dimension:
        raise RuntimeError("No valid embeddings were generated for the knowledge base.")

    if client.collection_exists(COLLECTION_NAME):
        existing_dimension, existing_distance = _collection_vector_config(
            client.get_collection(COLLECTION_NAME)
        )
        if existing_dimension != vector_dimension or existing_distance != models.Distance.COSINE:
            raise RuntimeError(
                "Qdrant collection is incompatible with the configured embedding model "
                f"(expected dimension {vector_dimension} and cosine distance). "
                "Use a compatible collection or migrate it explicitly."
            )
    else:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_dimension,
                distance=models.Distance.COSINE,
            ),
        )

    counts = {}
    for source_document, points in pending_points.items():
        desired_ids = {str(point.id) for point in points}
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        stale_ids = [
            point.id
            for point in _scroll_source_points(client, source_document)
            if str(point.id) not in desired_ids
        ]
        if stale_ids:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=stale_ids),
                wait=True,
            )
        counts[source_document] = len(points)
    return counts
