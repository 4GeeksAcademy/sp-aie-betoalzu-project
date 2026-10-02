from pathlib import Path
from types import SimpleNamespace

import pytest
from qdrant_client import models

from data.process import knowledge_base


class FakeQdrant:
    def __init__(self, *, dimension: int = 384, distance=models.Distance.COSINE):
        self.points = {}
        self.dimension = dimension
        self.distance = distance
        self.created = False

    def collection_exists(self, collection_name):
        return self.created

    def create_collection(self, collection_name, vectors_config):
        self.created = True
        self.dimension = vectors_config.size
        self.distance = vectors_config.distance

    def get_collection(self, collection_name):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=SimpleNamespace(size=self.dimension, distance=self.distance)
                )
            )
        )

    def scroll(self, collection_name, scroll_filter, limit, offset, with_payload, with_vectors):
        source_document = scroll_filter.must[0].match.value
        matches = [
            point
            for point in self.points.values()
            if point.payload["source_document"] == source_document
        ]
        return matches, None

    def upsert(self, collection_name, points, wait):
        for point in points:
            self.points[str(point.id)] = point

    def delete(self, collection_name, points_selector, wait):
        for point_id in points_selector.points:
            self.points.pop(str(point_id), None)


@pytest.fixture
def corpus_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(knowledge_base, "CORPUS_DIR", tmp_path)
    for _, filename in knowledge_base.SOURCE_DOCUMENTS:
        (tmp_path / filename).write_text(
            "# Documento\n\nPrimera regla comercial.\n\n"
            "Segunda regla y su condición.\n\nTercera excepción.",
            encoding="utf-8",
        )
    return tmp_path


def test_chunk_markdown_preserves_semantic_items_and_sections() -> None:
    markdown = (
        "# Servicios\n\n1. Búsqueda directa, evaluación por competencias y referencias.\n"
        "2. Equipos de soporte, con un mínimo de cinco agentes.\n\n"
        "## Condiciones\n\nLos tiempos son promedios, no garantías."
    )

    chunks = knowledge_base.chunk_markdown(markdown)

    assert len(chunks) == 3
    assert chunks[0][0] == "Servicios"
    assert "mínimo de cinco agentes" in chunks[1][1]
    assert chunks[2] == ("Condiciones", "Los tiempos son promedios, no garantías.")


def test_setup_indexes_all_documents_idempotently(
    corpus_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(knowledge_base, "embed", lambda text: [0.1] * 384)
    qdrant = FakeQdrant()

    first_counts = knowledge_base.setup(qdrant)
    first_ids = set(qdrant.points)
    second_counts = knowledge_base.setup(qdrant)

    assert first_counts == second_counts
    assert len(first_counts) == 4
    assert all(count >= 3 for count in first_counts.values())
    assert set(qdrant.points) == first_ids
    assert len(qdrant.points) == sum(first_counts.values())
    assert all(
        set(point.payload)
        == {"company", "source_document", "section", "language", "chunk_index", "text"}
        for point in qdrant.points.values()
    )


def test_setup_rejects_incompatible_collection_before_upserting(
    corpus_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(knowledge_base, "embed", lambda text: [0.1] * 384)
    qdrant = FakeQdrant(dimension=128)
    qdrant.created = True

    with pytest.raises(RuntimeError, match="incompatible"):
        knowledge_base.setup(qdrant)

    assert qdrant.points == {}