from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "support_agent_traces.json"
CASES: dict[str, dict[str, Any]] = {
    case["id"]: case
    for case in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
}


def completed_nodes(case: dict[str, Any]) -> list[str]:
    return [
        event["node_name"]
        for event in case["events"]
        if event["status"] == "completed"
    ]


def test_offline_fixtures_cover_three_distinct_outcomes() -> None:
    assert {"pricing-policy", "blank-question", "no-matching-context"} <= CASES.keys()


def test_pricing_trace_retrieves_before_nonempty_generation() -> None:
    case = CASES["pricing-policy"]

    assert completed_nodes(case) == [
        "receive_question",
        "retrieve_context",
        "generate_response",
    ]
    assert case["api_status"] == 200
    assert case["answer"].strip()
    assert case["events"][-1]["output"]["answer"] == case["answer"]


def test_blank_question_records_validation_and_returns_422() -> None:
    case = CASES["blank-question"]

    assert case["api_status"] == 422
    assert case["events"][-1]["output"]["error"] == "question_required"
    assert completed_nodes(case) == ["receive_question"]


def test_empty_retrieval_uses_explicit_abstention() -> None:
    case = CASES["no-matching-context"]
    retrieval = next(
        event for event in case["events"]
        if event["node_name"] == "retrieve_context"
        and event["status"] == "completed"
    )

    assert retrieval["output"] == {"chunk_count": 0, "references": []}
    assert completed_nodes(case) == [
        "receive_question",
        "retrieve_context",
        "answer_without_context",
    ]
    assert "base de conocimiento" in case["answer"].lower()
    assert case["events"][-1]["output"]["reason"] == "no_context"


def test_pricing_answer_is_anchored_to_the_real_knowledge_source() -> None:
    case = CASES["pricing-policy"]
    retrieval = next(
        event for event in case["events"]
        if event["node_name"] == "retrieve_context"
        and event["status"] == "completed"
    )
    reference = retrieval["output"]["references"][0]
    source_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "company-knowledge-base"
        / "nexova-pricing-model.es.md"
    )
    source_text = source_path.read_text(encoding="utf-8")

    assert "22%" in source_text
    assert "22%" in case["answer"]
    assert reference == {
        "source_document": "pricing-model",
        "section": "Headhunting ejecutivo",
    }
    assert "pricing-model" in case["answer"]
    assert "Headhunting ejecutivo" in case["answer"]
