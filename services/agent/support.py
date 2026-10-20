from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from data_project.pipelines.rag import generate_answer, retrieve


class AgentState(TypedDict):
    question: str
    context: list[dict[str, Any]]
    answer: str
    error: str | None
    run_id: str


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
                    datetime.now(timezone.utc).isoformat(),
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
) -> Callable[[AgentState], dict[str, Any]]:
    def run(state: AgentState) -> dict[str, Any]:
        traces.record(state["run_id"], node_name, "started", {})
        try:
            update, output = operation(state)
        except Exception:
            traces.record(
                state["run_id"],
                node_name,
                "failed",
                {"error": "node_failed"},
            )
            raise
        traces.record(state["run_id"], node_name, "completed", output)
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
    return "end" if state.get("error") else "retrieve_context"


def route_after_retrieve(state: AgentState) -> str:
    return "generate_response" if state.get("context") else "answer_without_context"


def build_support_graph(
    traces: TraceStore,
    *,
    retrieve_fn: Callable[[str], list[dict[str, Any]]] = retrieve,
    generate_fn: Callable[[str, list[dict[str, Any]]], str] = generate_answer,
    checkpointer: SqliteSaver,
):
    def receive_question(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        valid = bool(state["question"].strip())
        error = None if valid else "question_required"
        return {"error": error}, {"valid": valid, **({"error": error} if error else {})}

    def retrieve_context(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        context = retrieve_fn(state["question"].strip())
        return {"context": context}, {
            "chunk_count": len(context),
            "references": _chunk_references(context),
        }

    def generate_response(state: AgentState) -> tuple[dict[str, Any], dict[str, Any]]:
        answer = generate_fn(state["question"].strip(), state["context"]).strip()
        if not answer:
            raise RuntimeError("RAG generation returned an empty answer.")
        return {"answer": answer}, {"answer": answer}

    def answer_without_context(
        _state: AgentState,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        answer = (
            "Lo siento, la base de conocimiento no contiene información "
            "suficiente para responder esa pregunta."
        )
        return {"answer": answer}, {"reason": "no_context", "answer": answer}

    builder = StateGraph(AgentState)
    builder.add_node(
        "receive_question",
        _traced_node("receive_question", receive_question, traces),
    )
    builder.add_node(
        "retrieve_context",
        _traced_node("retrieve_context", retrieve_context, traces),
    )
    builder.add_node(
        "generate_response",
        _traced_node("generate_response", generate_response, traces),
    )
    builder.add_node(
        "answer_without_context",
        _traced_node("answer_without_context", answer_without_context, traces),
    )
    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges(
        "receive_question",
        route_after_receive,
        {"retrieve_context": "retrieve_context", "end": END},
    )
    builder.add_conditional_edges(
        "retrieve_context",
        route_after_retrieve,
        {
            "generate_response": "generate_response",
            "answer_without_context": "answer_without_context",
        },
    )
    builder.add_edge("generate_response", END)
    builder.add_edge("answer_without_context", END)

    graph = builder.compile(checkpointer=checkpointer)
    expected_nodes = {
        "receive_question",
        "retrieve_context",
        "generate_response",
        "answer_without_context",
    }
    compiled_nodes = set(graph.get_graph().nodes)
    if not expected_nodes.issubset(compiled_nodes):
        missing = sorted(expected_nodes - compiled_nodes)
        raise RuntimeError(f"Support-agent graph is missing required nodes: {missing}")
    return graph


class SupportAgent:
    def __init__(
        self,
        database_path: str | Path,
        *,
        retrieve_fn: Callable[[str], list[dict[str, Any]]] = retrieve,
        generate_fn: Callable[[str, list[dict[str, Any]]], str] = generate_answer,
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
            checkpointer=self.checkpointer,
        )

    def invoke(self, question: str) -> AgentState:
        run_id = str(uuid4())
        return self.graph.invoke(
            {
                "question": question,
                "context": [],
                "answer": "",
                "error": None,
                "run_id": run_id,
            },
            {
                "configurable": {"thread_id": f"support-agent:{run_id}"},
                "metadata": {"run_id": run_id},
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
