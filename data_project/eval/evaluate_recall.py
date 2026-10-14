#!/usr/bin/env python3
"""Evaluate Recall@3 for the RAG retrieval pipeline.

Reads ``data_project/eval/test-queries.json`` and for each question runs
``retrieve(k=3)``, then checks whether the expected source documents
appear in the returned payloads.

Usage:
    uv run python data_project/eval/evaluate_recall.py

Exit code:
    0  — Recall@3 ≥ 80 %
    1  — Recall@3 < 80 %
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from data_project.pipelines.rag import retrieve
from data_project.process.knowledge_base import setup

HERE = Path(__file__).resolve().parent
QUERIES_PATH = HERE / "test-queries.json"
RECALL_THRESHOLD = 0.80  # 80 %


def load_queries() -> list[dict]:
    with open(QUERIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate() -> dict:
    queries = load_queries()
    results = []

    for entry in queries:
        question = entry["question"]
        expected_sources = set(entry["relevant_sources"])

        hits = retrieve(question, k=3)
        retrieved_sources = {h["source_document"] for h in hits if h.get("source_document")}

        matched = bool(expected_sources & retrieved_sources)
        results.append(
            {
                "question": question,
                "expected_sources": sorted(expected_sources),
                "retrieved_sources": sorted(retrieved_sources),
                "matched": matched,
            }
        )

    total = len(results)
    matched_count = sum(1 for r in results if r["matched"])
    recall = matched_count / total if total > 0 else 0.0

    return {
        "total_queries": total,
        "matched_queries": matched_count,
        "recall_at_3": round(recall, 4),
        "threshold": RECALL_THRESHOLD,
        "passed": recall >= RECALL_THRESHOLD,
        "details": results,
    }


def print_report(report: dict) -> None:
    print("=" * 60)
    print("  Evaluación Recall@3 — Base de Conocimiento Nexova")
    print("=" * 60)
    print(f"\n  Total consultas          : {report['total_queries']}")
    print(f"  Consultas con acierto    : {report['matched_queries']}")
    print(f"  Recall@3                 : {report['recall_at_3']:.1%}")
    print(f"  Umbral requerido         : {report['threshold']:.0%}")
    print(f"  Resultado                : {'✅ PASÓ' if report['passed'] else '❌ NO PASÓ'}")
    print()

    for i, detail in enumerate(report["details"], 1):
        status = "✅" if detail["matched"] else "❌"
        print(f"  {i}. {status} {detail['question']}")
        print(f"     Esperados: {', '.join(detail['expected_sources'])}")
        print(f"     Obtenidos: {', '.join(detail['retrieved_sources'])}")
        print()

    print("=" * 60)


def main() -> int:
    # Ensure the index is populated before evaluating
    print("Ejecutando indexación previa...")
    try:
        result = setup()
        print(f"  Documentos indexados: {result}")
    except RuntimeError as exc:
        print(f"  ⚠️  Indexación falló: {exc}")
        print("  Se evaluará con los datos existentes en Qdrant.")

    print()
    report = evaluate()
    print_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())