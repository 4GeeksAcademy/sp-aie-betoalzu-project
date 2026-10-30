"""Contract tests for the RAG pipeline (data_project/pipelines/rag.py).

All external dependencies (Qdrant, LLM HTTP) are replaced with test doubles
so these tests are fast, deterministic and safe to run without credentials.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from data_project.pipelines import rag


# ── Fakes ────────────────────────────────────────────────────────────────

class FakeQdrantClient:
    """Minimal in-memory Qdrant stub that returns pre-loaded points on search."""

    def __init__(self, points: list[dict[str, Any]] | None = None) -> None:
        self._points = points or []

    def query_points(self, **kwargs) -> list[Any]:
        # Return simple namespace objects mimicking Qdrant hit
        hits: list[Any] = []
        for p in self._points:
            score = kwargs.get("score_threshold", 0.0)
            # Always return points if they exist (simplified)
            hit = MagicMock()
            hit.payload = p
            hit.score = 0.95
            hits.append(hit)
        if kwargs.get("limit"):
            return hits[: kwargs["limit"]]
        return MagicMock(points=hits)


class FakeResponse:
    """Mimics requests.Response for the LLM call."""

    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json = json_data or {
            "choices": [{"message": {"content": "Respuesta simulada del asistente."}}]
        }

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if not self.ok:
            raise Exception(f"HTTP {self.status_code}")


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_chunks() -> list[dict[str, Any]]:
    return [
        {
            "company": "Nexova",
            "source_document": "nexova-pricing-model",
            "section": "Honorarios",
            "language": "es",
            "chunk_index": 0,
            "text": "La tarifa de Nexova es del 22% sobre el salario base del candidato.",
        },
        {
            "company": "Nexova",
            "source_document": "nexova-service-lines",
            "section": "Garantía",
            "language": "es",
            "chunk_index": 0,
            "text": "La garantía de reemplazo es de 6 meses desde la fecha de inicio.",
        },
    ]


@pytest.fixture
def fake_qdrant(sample_chunks: list[dict[str, Any]]) -> FakeQdrantClient:
    return FakeQdrantClient(sample_chunks)


# ── retrieve() ───────────────────────────────────────────────────────────

class TestRetrieve:
    def test_returns_empty_list_for_blank_query(self) -> None:
        assert rag.retrieve("") == []
        assert rag.retrieve("   ") == []

    def test_returns_payloads_from_qdrant(
        self, fake_qdrant: FakeQdrantClient
    ) -> None:
        with patch.object(rag, "embed", return_value=[0.1] * 384):
            results = rag.retrieve("¿Cuál es la tarifa?", _client=fake_qdrant)  # type: ignore[arg-type]

        assert len(results) == 2
        assert results[0]["source_document"] == "nexova-pricing-model"
        assert results[1]["section"] == "Garantía"

    def test_respects_k_parameter(self, fake_qdrant: FakeQdrantClient) -> None:
        with patch.object(rag, "embed", return_value=[0.1] * 384):
            results = rag.retrieve("test", k=1, _client=fake_qdrant)  # type: ignore[arg-type]

        assert len(results) == 1

    def test_never_returns_scores_in_payload(
        self, fake_qdrant: FakeQdrantClient
    ) -> None:
        with patch.object(rag, "embed", return_value=[0.1] * 384):
            results = rag.retrieve("test", _client=fake_qdrant)  # type: ignore[arg-type]

        for r in results:
            assert "score" not in r
            assert "vector" not in r

    def test_uses_default_score_threshold(self) -> None:
        client = MagicMock()
        client.query_points.return_value = MagicMock(points=[])
        with patch.object(rag, "embed", return_value=[0.1] * 384):
            rag.retrieve("test", _client=client)  # type: ignore[arg-type]
        assert client.query_points.call_args.kwargs["score_threshold"] == 0.5

    def test_explicit_score_threshold_overrides_default(self) -> None:
        client = MagicMock()
        client.query_points.return_value = MagicMock(points=[])
        with patch.object(rag, "embed", return_value=[0.1] * 384):
            rag.retrieve("test", min_score=0.73, _client=client)  # type: ignore[arg-type]
        assert client.query_points.call_args.kwargs["score_threshold"] == 0.73


# ── generate_answer() ────────────────────────────────────────────────────

class TestGenerateAnswer:
    def test_abstains_when_context_empty(self) -> None:
        answer = rag.generate_answer("¿Cuál es la tarifa?", [])
        assert "base de conocimiento" in answer.lower() or "suficiente" in answer.lower()
        assert len(answer) > 20

    def test_calls_llm_and_returns_answer(
        self, sample_chunks: list[dict[str, Any]]
    ) -> None:
        with patch.object(rag, "_load_llm_config", return_value=("http://fake", "gpt-4o-mini", "sk-fake")):
            with patch("data_project.pipelines.rag.requests.post", return_value=FakeResponse()) as mock_post:
                answer = rag.generate_answer("¿Cuál es la tarifa?", sample_chunks)

        assert answer == "Respuesta simulada del asistente."

        # Verify the LLM was called with the correct prompt
        call_kwargs = mock_post.call_args[1]
        messages = call_kwargs["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "nexova-pricing-model" in messages[1]["content"]
        assert "22%" in messages[1]["content"]
        assert call_kwargs["json"]["temperature"] == 0.3

    def test_raises_on_llm_auth_error(self, sample_chunks: list[dict[str, Any]]) -> None:
        with patch.object(rag, "_load_llm_config", return_value=("http://fake", "gpt-4o-mini", "bad-key")):
            with patch("data_project.pipelines.rag.requests.post", return_value=FakeResponse(status_code=401)):
                with pytest.raises(RuntimeError, match="authentication"):
                    rag.generate_answer("test", sample_chunks)

    def test_raises_on_non_ok_llm_response(self, sample_chunks: list[dict[str, Any]]) -> None:
        with patch.object(rag, "_load_llm_config", return_value=("http://fake", "gpt-4o-mini", "sk-fake")):
            with patch("data_project.pipelines.rag.requests.post", return_value=FakeResponse(status_code=500)):
                with pytest.raises(RuntimeError, match="HTTP 500"):
                    rag.generate_answer("test", sample_chunks)

    def test_raises_on_malformed_llm_response(self, sample_chunks: list[dict[str, Any]]) -> None:
        bad_json = {"unexpected": "structure"}
        with patch.object(rag, "_load_llm_config", return_value=("http://fake", "gpt-4o-mini", "sk-fake")):
            with patch(
                "data_project.pipelines.rag.requests.post",
                return_value=FakeResponse(status_code=200, json_data=bad_json),
            ):
                with pytest.raises(RuntimeError, match="invalid response"):
                    rag.generate_answer("test", sample_chunks)


# ── query() ──────────────────────────────────────────────────────────────

class TestQuery:
    def test_composes_retrieve_and_generate(self) -> None:
        with patch.object(rag, "retrieve", return_value=[{"source_document": "test", "section": "X", "text": "Dummy"}]) as mock_retrieve:
            with patch.object(rag, "generate_answer", return_value="Answer") as mock_generate:
                result = rag.query("¿Hola?")

        assert result == "Answer"
        mock_retrieve.assert_called_once_with("¿Hola?")
        mock_generate.assert_called_once_with("¿Hola?", [{"source_document": "test", "section": "X", "text": "Dummy"}])