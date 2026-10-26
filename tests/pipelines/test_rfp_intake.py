from __future__ import annotations

import sys
import types

import pytest

from data_project.pipelines.rfp_intake import graph


@pytest.mark.parametrize(
    ("text", "valid"),
    [
        ("RFP formal: solicitamos una búsqueda ejecutiva.", True),
        ("Correo informal: nos pueden enviar una propuesta de soporte.", True),
        ("Pitch del proveedor ATS sobre su plataforma.", False),
    ],
)
def test_classifier_decisions_are_structured(monkeypatch, text: str, valid: bool) -> None:
    from data_project.pipelines.rfp_intake.graph import Classification

    def fake_agent(_name, _instruction, payload, _model):
        assert payload["markdown"] == text
        return Classification(
            is_rfp=valid,
            reason="Solicita propuesta." if valid else "Es una oferta de proveedor.",
            evidence=text,
        )

    monkeypatch.setattr(graph, "_invoke_json_agent", fake_agent)
    result = graph._classify_rfp({"markdown": text})
    assert result["classification"]["is_rfp"] is valid


def test_worker_receives_only_relevant_excerpt_and_keeps_missing_volume_open(monkeypatch):
    from data_project.pipelines.rfp_intake.graph import WorkerOutput

    observed: dict = {}

    def fake_agent(_name, _instruction, payload, _model):
        observed.update(payload)
        return WorkerOutput(
            key_aspects=[
                {
                    "aspect": "Número de agentes",
                    "value": None,
                    "evidence": "",
                    "open_question": "¿Cuántos agentes solicita el cliente?",
                }
            ],
            open_questions=["¿Cuántos agentes solicita el cliente?"],
        )

    monkeypatch.setattr(graph, "_invoke_json_agent", fake_agent)
    result = graph._department_worker(
        {
            "department_id": "soporte",
            "metadata": {
                "scope": None,
                "departments_needed": ["soporte"],
                "department_extracts": {
                    "seleccion": "Extracto de búsqueda ejecutiva",
                    "soporte": "Servicio de atención al cliente 24/7.",
                },
            },
            "excerpt": "Servicio de atención al cliente 24/7.",
        }
    )

    assert observed["department_id"] == "soporte"
    assert observed["relevant_excerpt"] == "Servicio de atención al cliente 24/7."
    assert "department_extracts" not in observed["metadata"]
    aspect = result["worker_results"][0]["key_aspects"][0]
    assert aspect["value"] is None
    assert aspect["open_question"] == "¿Cuántos agentes solicita el cliente?"


def test_graph_converts_pdf_before_classification_and_rejects_vendor_pitch(
    tmp_path, monkeypatch
):
    raw_dir = tmp_path / "raw"
    process_dir = tmp_path / "process"
    raw_dir.mkdir()
    pdf_path = raw_dir / "ticket.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    monkeypatch.setattr(graph, "RAW_DIR", raw_dir)
    monkeypatch.setattr(graph, "PROCESS_DIR", process_dir)

    order: list[str] = []

    class FakeMarkItDown:
        def convert(self, path: str):
            assert path == str(pdf_path)
            order.append("converted")
            return types.SimpleNamespace(text_content="Oferta de proveedor ATS.")

    monkeypatch.setitem(
        sys.modules,
        "markitdown",
        types.SimpleNamespace(MarkItDown=FakeMarkItDown),
    )

    def fake_agent(_name, _instruction, payload, _model):
        assert order == ["converted"]
        assert payload["markdown"] == "Oferta de proveedor ATS."
        order.append("classified")
        return graph.Classification(
            is_rfp=False,
            reason="Oferta de proveedor.",
            evidence="Oferta de proveedor ATS.",
        )

    monkeypatch.setattr(graph, "_invoke_json_agent", fake_agent)
    result = graph.run_rfp_intake(pdf_path, "ticket-1")

    assert order == ["converted", "classified"]
    assert result["status"] == "descartado"
    assert result["classification"]["evidence"] == "Oferta de proveedor ATS."


def test_readability_metrics_report_units_and_limitations():
    metrics = graph._readability_metrics("Solicitamos apoyo. Necesitamos una propuesta.")

    assert metrics["word_count"] == 5
    assert metrics["sentence_count"] == 2
    assert metrics["average_words_per_sentence"] == 2.5
    assert "unit" in metrics
    assert "limitation" in metrics
