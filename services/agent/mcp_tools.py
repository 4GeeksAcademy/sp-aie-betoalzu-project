from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.shared.exceptions import McpError
from pydantic import TypeAdapter, ValidationError

from services.agent.tools import (
    IncidentQuery,
    IncidentResult,
    InventoryQuery,
    InventoryResult,
    SourceError,
)
from services.api.incidents.models import IncidentOut
from services.api.inventory.models import AssetResponse

logger = logging.getLogger(__name__)
MCP_TIMEOUT = 4.0


class _SourceFailure(Exception):
    def __init__(self, code: SourceError | Literal["not_found"]) -> None:
        self.code = code
        super().__init__(code)


def _connection_config() -> dict[str, Any]:
    url = os.getenv("SUPPORT_AGENT_MCP_URL", "").strip()
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise _SourceFailure("not_configured")
    token = os.getenv("SUPPORT_AGENT_MCP_ACCESS_TOKEN", "").strip()
    if not token:
        raise _SourceFailure("not_configured")
    return {
        "transport": "streamable_http",
        "url": url,
        "headers": {"Authorization": f"Bearer {token}"},
        "timeout": MCP_TIMEOUT,
        "sse_read_timeout": MCP_TIMEOUT,
    }


def _decode_tool_result(result: object) -> dict[str, Any]:
    if isinstance(result, tuple) and len(result) == 2:
        content, artifact = result
        structured = getattr(artifact, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        result = content
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            payload = json.loads(result)
        except json.JSONDecodeError as exc:
            raise _SourceFailure("invalid_response") from exc
        if isinstance(payload, dict):
            return payload
    if isinstance(result, list):
        blocks = [
            item["text"]
            for item in result
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if blocks:
            return _decode_tool_result("\n".join(blocks))
    raise _SourceFailure("invalid_response")


def _raise_tool_error(payload: dict[str, Any]) -> None:
    code = payload.get("error_code")
    if not isinstance(code, str):
        return
    if code in {"INCIDENT_NOT_FOUND", "PRODUCT_NOT_FOUND"}:
        raise _SourceFailure("not_found")
    if code in {"AUTHENTICATION_REQUIRED", "INVALID_ACCESS_TOKEN"}:
        raise _SourceFailure("authentication_failed")
    if code == "INSUFFICIENT_SCOPE":
        raise _SourceFailure("authorization_failed")
    if code == "UPSTREAM_TIMEOUT":
        raise _SourceFailure("timeout")
    if code in {"INVALID_INPUT", "INVALID_UPSTREAM_RESPONSE"}:
        raise _SourceFailure("invalid_response")
    logger.warning("Support-agent MCP tool failed (error_code=%s)", code)
    raise _SourceFailure("service_error")


def _invoke_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    connection = _connection_config()

    async def invoke() -> object:
        client = MultiServerMCPClient(
            {"nexova": connection},
            tool_name_prefix=False,
            handle_tool_errors=False,
        )
        tools = await client.get_tools(server_name="nexova")
        tool = next((item for item in tools if item.name == tool_name), None)
        if tool is None:
            raise _SourceFailure("invalid_response")
        return await tool.ainvoke(arguments)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise _SourceFailure("service_error")

    try:
        result = asyncio.run(invoke())
    except _SourceFailure:
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise _SourceFailure("timeout") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise _SourceFailure("authentication_failed") from exc
        if exc.response.status_code == 403:
            raise _SourceFailure("authorization_failed") from exc
        raise _SourceFailure("service_error") from exc
    except (httpx.RequestError, McpError, ToolException, OSError) as exc:
        raise _SourceFailure("service_error") from exc
    except (TypeError, ValueError, ValidationError) as exc:
        raise _SourceFailure("invalid_response") from exc
    return _decode_tool_result(result)


def query_incidents(query: IncidentQuery) -> IncidentResult:
    try:
        payload = _invoke_mcp_tool(
            "incidents_get",
            query.model_dump(mode="json", exclude_none=True),
        )
        _raise_tool_error(payload)
        incidents = TypeAdapter(list[IncidentOut]).validate_python(
            payload.get("incidents"),
        )
        status = payload.get("status")
        if status not in {"success", "not_found"}:
            raise _SourceFailure("invalid_response")
        return IncidentResult(status=status, incidents=incidents)
    except _SourceFailure as exc:
        if exc.code == "not_found":
            return IncidentResult(status="not_found")
        error = exc.code
    except (TypeError, ValueError, ValidationError):
        error = "invalid_response"
    logger.warning("Support-agent source failed (source=incidents, error=%s)", error)
    return IncidentResult(status="failed", error=error)


def query_inventory(query: InventoryQuery) -> InventoryResult:
    try:
        payload = _invoke_mcp_tool(
            "inventory_get_products",
            query.model_dump(mode="json", exclude_none=True),
        )
        _raise_tool_error(payload)
        products = TypeAdapter(list[AssetResponse]).validate_python(
            payload.get("products"),
        )
        if any("current_stock" not in item.model_fields_set for item in products):
            raise _SourceFailure("invalid_response")
        status = payload.get("status")
        if status not in {"success", "not_found"}:
            raise _SourceFailure("invalid_response")
        return InventoryResult(status=status, products=products)
    except _SourceFailure as exc:
        if exc.code == "not_found":
            return InventoryResult(status="not_found")
        error = exc.code
    except (TypeError, ValueError, ValidationError):
        error = "invalid_response"
    logger.warning("Support-agent source failed (source=inventory, error=%s)", error)
    return InventoryResult(status="failed", error=error)
