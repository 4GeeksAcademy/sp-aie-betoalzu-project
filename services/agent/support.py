from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

import requests
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from data_project.pipelines.rag import generate_answer, retrieve
from services.agent.mcp_tools import query_incidents, query_inventory
from services.agent.routing import QueryPlan, Source, plan_question
from services.agent.tools import (
    IncidentQuery,
    IncidentResult,
    InventoryQuery,
    InventoryResult,
)

logger = logging.getLogger(__name__)
RAG_FAILURES = (RuntimeError, requests.RequestException, UnexpectedResponse, ResponseHandlingException)


class AgentState(TypedDict):
    question: str
    context: list[dict[str, Any]]
    answer: str
    error: str | None
    run_id: str
    plan: QueryPlan
    incident_result: dict[str, Any]
    inventory_result: dict[str, Any]
    rag_status: str


class TraceEvent(TypedDict):
    run_id: str
    sequence: int
    node_name: str
    status: str
    timestamp: str
    output: dict[str, Any]


class TraceStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS support_agent_traces (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    node_name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
                    timestamp TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, timeout=30)

    def record(
        self,
        run_id: str,
        node_name: str,
        status: str,
        output: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM support_agent_traces
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO support_agent_traces
                    (run_id, sequence, node_name, status, timestamp, output_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    node_name,
                    status,
                    datetime.now(UTC).isoformat(),
                    json.dumps(output, ensure_ascii=False),
                ),
            )

    def get(self, run_id: str) -> list[TraceEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, node_name, status, timestamp, output_json
                FROM support_agent_traces
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "run_id": run_id,
                "sequence": sequence,
                "node_name": node_name,
                "status": status,
                "timestamp": timestamp,
                "output": json.loads(output_json),
            }
            for sequence, node_name, status, timestamp, output_json in rows
        ]


NodeOperation = Callable[[AgentState], tuple[dict[str, Any], dict[str, Any]]]


def _traced_node(
    node_name: str,
    operation: NodeOperation,
    traces: TraceStore,
    source: Source | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    def run(state: AgentState) -> dict[str, Any]:
        source_output = {"source": source} if source else {}
        traces.record(state["run_id"], node_name, "started", source_output)
        try:
            update, output = operation(state)
        except Exception:
            traces.record(
                state["run_id"],
                node_name,
                "failed",
                {**source_output, "outcome": "failed", "error": "node_failed"},
            )
            raise
        traces.record(state["run_id"], node_name, "completed", {**source_output, **output})
        return update

    return run


def _chunk_references(context: list[dict[str, Any]]) -> list[dict[str, str | int]]:
    references: list[dict[str, str | int]] = []
    for chunk in context:
        reference: dict[str, str | int] = {}
        for key in ("source_document", "section", "id", "chunk_id"):
            value = chunk.get(key)
            if isinstance(value, (str, int)):
                reference[key] = value
        references.append(reference)
    return references


def route_after_receive(state: AgentState) -> str:
    if state.get("error"):
        return "end"
    sources = state.get("plan", {}).get("sources", ["rag"])
    if "incidents" in sources:
        return "consult_incidents"
    if "inventory" in sources:
        return "consult_inventory"
    return "retrieve_context"


def route_after_incidents(state: AgentState) -> str:
    if "inventory" in state["plan"]["sources"]:
        return "consult_inventory"
    return route_after_inventory(state)


def route_after_inventory(state: AgentState) -> str:
    return "retrieve_context" if "rag" in state["plan"]["sources"] else "compose_response"


def route_after_answer(state: AgentState) -> str:
    sources = state.get("plan", {}).get("sources", ["rag"])
    return "compose_response" if any(source != "rag" for source in sources) else "end"


def route_after_retrieve(state: AgentState) -> str:
    return "generate_response" if state.get("context") else "answer_without_context"


def build_support_graph(
    traces: TraceStore,
    *,
    retrieve_fn: Callable[[str], list[dict[str, Any]]] = retrieve,
    generate_fn: Callable[[str, list[dict[str, Any]]], str] = generate_answer,
    incidents_fn: Callable[[IncidentQuery], IncidentResult] = query_incidents,
    inventory_fn: Callable[[InventoryQuery], InventoryResult] = query_inventory,
    checkpointer: SqliteSaver,
):
    def receive_question(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        valid = bool(state["question"].strip())
        error = None if valid else "question_required"
        if not valid:
            return {"error": error}, {"valid": False, "error": error}
        plan = plan_question(state["question"])
        return {"error": None, "plan": plan}, {"valid": True, "sources": plan["sources"]}

    def consult_incidents(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        result = incidents_fn(IncidentQuery.model_validate(state["plan"]["incident_query"]))
        return {"incident_result": result.model_dump(mode="json")}, {
            "outcome": result.status,
            "references": [
                {"id": item.id, "ticket_id": item.ticket_id}
                for item in result.incidents
            ],
            "error": result.error,
        }

    def consult_inventory(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        result = inventory_fn(InventoryQuery.model_validate(state["plan"]["inventory_query"]))
        return {"inventory_result": result.model_dump(mode="json")}, {
            "outcome": result.status,
            "references": [{"id": item.id, "sku": item.sku} for item in result.products],
            "error": result.error,
        }

    def retrieve_context(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            context = retrieve_fn(state["question"].strip())
        except RAG_FAILURES:
            if route_after_answer(state) == "end":
                raise
            logger.warning("Support-agent source failed (source=rag, stage=retrieve)")
            return {"context": [], "rag_status": "failed"}, {
                "outcome": "failed", "error": "source_failed", "references": [],
            }
        outcome = "success" if context else "not_found"
        return {"context": context, "rag_status": outcome}, {
            "outcome": outcome,
            "chunk_count": len(context),
            "references": _chunk_references(context),
        }

    def generate_response(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        question = state["question"].strip()
        mixed = route_after_answer(state) != "end"
        if mixed:
            question = (
                "Explica solo el conocimiento documental aplicable, sin afirmar "
                "estados actuales de tickets ni stock de productos. Consulta: " + question
            )
        try:
            answer = generate_fn(question, state["context"]).strip()
            if not answer:
                raise RuntimeError("RAG generation returned an empty answer.")
        except RAG_FAILURES:
            if not mixed:
                raise
            logger.warning("Support-agent source failed (source=rag, stage=generate)")
            return {
                "answer": "No pude consultar la información documental ahora mismo.",
                "rag_status": "failed",
            }, {"outcome": "failed", "error": "source_failed"}
        return {"answer": answer}, {"outcome": "success", **(
            {"answer_length": len(answer)} if mixed else {"answer": answer}
        )}

    def answer_without_context(
        state: AgentState,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        failed = state.get("rag_status") == "failed"
        answer = "No pude consultar la información documental ahora mismo." if failed else (
            "Lo siento, la base de conocimiento no contiene información "
            "suficiente para responder esa pregunta."
        )
        return {"answer": answer}, {
            "outcome": "failed" if failed else "not_found",
            "reason": "source_failed" if failed else "no_context", "answer": answer,
        }

    def compose_response(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        parts: list[str] = []
        sources = state["plan"]["sources"]
        if "incidents" in sources:
            incidents = IncidentResult.model_validate(state["incident_result"])
            if incidents.status == "failed":
                parts.append("No pude confirmar los datos ni el estado de los tickets ahora mismo.")
            elif incidents.status == "not_found":
                parts.append("No encontré tickets que coincidan con la consulta; no puedo confirmar su estado.")
            else:
                parts.append("Incidentes confirmados (fuente: incidents):\n" + "\n".join(
                    f"- Ticket {item.ticket_id or item.id} (ID {item.id}): "
                    f"estado={item.status}; categoría={item.category}; origen={item.origin}; "
                    f"sede={item.branch}; creado={item.created_at}; actualizado={item.updated_at}."
                    for item in incidents.incidents
                ))
        if "inventory" in sources:
            inventory = InventoryResult.model_validate(state["inventory_result"])
            if inventory.status == "failed":
                parts.append("No pude confirmar el stock del inventario ahora mismo.")
            elif inventory.status == "not_found":
                parts.append("No encontré productos que coincidan; no puedo confirmar su stock.")
            else:
                parts.append("Inventario confirmado (fuente: inventory):\n" + "\n".join(
                    f"- Producto {item.id}: {item.name} ({item.sku}); "
                    f"stock={item.current_stock}; sede={item.office.value}."
                    for item in inventory.products
                ))
        if "rag" in sources:
            parts.append("Información documental (fuente: rag):\n" + state["answer"])
        answer = "\n\n".join(parts)
        return {"answer": answer}, {"sources": sources, "answer_length": len(answer)}

    builder = StateGraph(AgentState)
    builder.add_node(
        "receive_question",
        _traced_node("receive_question", receive_question, traces),
    )
    builder.add_node(
        "retrieve_context",
        _traced_node("retrieve_context", retrieve_context, traces, "rag"),
    )
    builder.add_node(
        "generate_response",
        _traced_node("generate_response", generate_response, traces, "rag"),
    )
    builder.add_node(
        "answer_without_context",
        _traced_node("answer_without_context", answer_without_context, traces, "rag"),
    )
    builder.add_node("consult_incidents", _traced_node(
        "consult_incidents", consult_incidents, traces, "incidents",
    ))
    builder.add_node("consult_inventory", _traced_node(
        "consult_inventory", consult_inventory, traces, "inventory",
    ))
    builder.add_node("compose_response", _traced_node(
        "compose_response", compose_response, traces,
    ))
    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges(
        "receive_question",
        route_after_receive,
        {
            "retrieve_context": "retrieve_context", "end": END,
            "consult_incidents": "consult_incidents", "consult_inventory": "consult_inventory",
        },
    )
    builder.add_conditional_edges("consult_incidents", route_after_incidents, {
        node: node for node in ("consult_inventory", "retrieve_context", "compose_response")
    })
    builder.add_conditional_edges("consult_inventory", route_after_inventory, {
        node: node for node in ("retrieve_context", "compose_response")
    })
    builder.add_conditional_edges(
        "retrieve_context",
        route_after_retrieve,
        {
            "generate_response": "generate_response",
            "answer_without_context": "answer_without_context",
        },
    )
    for node in ("generate_response", "answer_without_context"):
        builder.add_conditional_edges(node, route_after_answer, {
            "compose_response": "compose_response", "end": END,
        })
    builder.add_edge("compose_response", END)

    graph = builder.compile(checkpointer=checkpointer)
    expected_nodes = {
        "receive_question",
        "retrieve_context",
        "generate_response",
        "answer_without_context",
        "consult_incidents",
        "consult_inventory",
        "compose_response",
    }
    compiled_nodes = set(graph.get_graph().nodes)
    if not expected_nodes.issubset(compiled_nodes):
        missing = sorted(expected_nodes - compiled_nodes)
        raise RuntimeError(f"Support-agent graph is missing required nodes: {missing}")
    expected_edges = {
        ("__start__", "receive_question"),
        ("receive_question", "retrieve_context"),
        ("receive_question", "__end__"),
        ("retrieve_context", "generate_response"),
        ("retrieve_context", "answer_without_context"),
        ("generate_response", "__end__"),
        ("answer_without_context", "__end__"),
        ("receive_question", "consult_incidents"),
        ("receive_question", "consult_inventory"),
        ("consult_incidents", "consult_inventory"),
        ("consult_incidents", "retrieve_context"),
        ("consult_incidents", "compose_response"),
        ("consult_inventory", "retrieve_context"),
        ("consult_inventory", "compose_response"),
        ("generate_response", "compose_response"),
        ("answer_without_context", "compose_response"),
        ("compose_response", "__end__"),
    }
    compiled_edges = {
        (edge.source, edge.target)
        for edge in graph.get_graph().edges
    }
    if not expected_edges.issubset(compiled_edges):
        missing = sorted(expected_edges - compiled_edges)
        raise RuntimeError(
            f"Support-agent graph has missing or disconnected routes: {missing}"
        )
    return graph


class SupportAgent:
    def __init__(
        self,
        database_path: str | Path,
        *,
        retrieve_fn: Callable[[str], list[dict[str, Any]]] = retrieve,
        generate_fn: Callable[[str, list[dict[str, Any]]], str] = generate_answer,
        incidents_fn: Callable[[IncidentQuery], IncidentResult] = query_incidents,
        inventory_fn: Callable[[InventoryQuery], InventoryResult] = query_inventory,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
            timeout=30,
        )
        self.checkpointer = SqliteSaver(self._checkpoint_connection)
        self.checkpointer.setup()
        self.traces = TraceStore(self.database_path)
        self.graph = build_support_graph(
            self.traces,
            retrieve_fn=retrieve_fn,
            generate_fn=generate_fn,
            incidents_fn=incidents_fn,
            inventory_fn=inventory_fn,
            checkpointer=self.checkpointer,
        )

    def invoke(self, question: str, *, run_id: str | None = None) -> AgentState:
        execution_id = run_id or str(uuid4())
        return self.graph.invoke(
            {
                "question": question,
                "context": [],
                "answer": "",
                "error": None,
                "run_id": execution_id,
            },
            {
                "configurable": {"thread_id": f"support-agent:{execution_id}"},
                "metadata": {"run_id": execution_id},
            },
        )

    def get_state(self, run_id: str):
        return self.graph.get_state(
            {"configurable": {"thread_id": f"support-agent:{run_id}"}}
        )

    def get_trace(self, run_id: str) -> list[TraceEvent]:
        return self.traces.get(run_id)

    def close(self) -> None:
        self._checkpoint_connection.close()


_agent: SupportAgent | None = None


def initialize_support_agent() -> None:
    global _agent
    if _agent is not None:
        raise RuntimeError("Support agent has already been initialized.")
    root = Path(__file__).resolve().parents[2]
    database_path = os.getenv(
        "SUPPORT_AGENT_DB_PATH",
        str(root / "data_project" / "support-agent.sqlite3"),
    )
    try:
        _agent = SupportAgent(database_path)
    except Exception as exc:
        raise RuntimeError(
            "Unable to initialize the support-agent graph or SQLite store. "
            "Check SUPPORT_AGENT_DB_PATH permissions and LangGraph setup."
        ) from exc


def shutdown_support_agent() -> None:
    global _agent
    if _agent is not None:
        _agent.close()
        _agent = None


def get_support_agent() -> SupportAgent:
    if _agent is None:
        raise RuntimeError("Support agent is not initialized.")
    return _agent
