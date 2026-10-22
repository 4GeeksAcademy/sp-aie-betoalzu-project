from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

from mcpauth import MCPAuth
from mcpauth.config import (
    AuthorizationServerMetadata,
    AuthServerConfig,
    AuthServerType,
)
from mcpauth.exceptions import (
    BearerAuthExceptionCode,
    MCPAuthBearerAuthException,
)
from mcpauth.types import AuthInfo

from mcps.server import (
    SUPPORTED_SCOPES,
    TOOL_SCOPES,
    ToolScopeMiddleware,
    _resource_metadata_route,
    build_app,
    create_mcp_server,
)


def test_discovery_exposes_six_tools_with_parameters_and_required_scopes():
    auth = SimpleNamespace(auth_info=None)
    tools = asyncio.run(create_mcp_server(auth).list_tools())

    assert {tool.name for tool in tools} == set(TOOL_SCOPES)
    for tool in tools:
        assert tool.description
        assert TOOL_SCOPES[tool.name] in tool.description
        assert tool.inputSchema["type"] == "object"

    by_name = {tool.name: tool for tool in tools}
    create_schema = by_name["incidents_create"].inputSchema
    update_schema = by_name["incidents_update"].inputSchema
    transition_schema = by_name["incidents_transition_status"].inputSchema
    inventory_schema = by_name["inventory_write_attempt"].inputSchema
    assert "status" not in create_schema["properties"]
    assert "status" not in update_schema["properties"]
    assert set(create_schema["required"]) == {"title", "category", "origin"}
    assert transition_schema["properties"]["status"]
    assert "current_stock" in by_name["inventory_get_products"].description
    assert "incidents" in by_name["incidents_get"].description
    create_schema_json = json.dumps(create_schema)
    transition_schema_json = json.dumps(transition_schema)
    inventory_schema_json = json.dumps(inventory_schema)
    assert all(value in create_schema_json for value in (
        "technical_failure", "process_error", "customer", "valencia_operations",
    ))
    assert all(value in transition_schema_json for value in (
        "open", "in_progress", "resolved", "discarded",
    ))
    assert all(value in inventory_schema_json for value in (
        "create_product", "update_product", "delete_product",
        "create_inbound_order", "create_outbound_order",
    ))
    assert set(SUPPORTED_SCOPES) == {
        "incidents:read", "incidents:write", "inventory:read",
    }
    assert "INVENTORY_READ_ONLY" in by_name["inventory_write_attempt"].description
    assert "operation" in inventory_schema["properties"]


def test_inventory_write_attempt_is_denied_without_http_side_effects(monkeypatch):
    monkeypatch.setattr(
        "mcps.backend.requests.request",
        Mock(side_effect=AssertionError("inventory write must not call HTTP")),
    )
    auth = SimpleNamespace(auth_info=SimpleNamespace(
        client_id="test-client",
        subject="test-subject",
        scopes=["inventory:read"],
    ))
    _content, structured = asyncio.run(
        create_mcp_server(auth).call_tool(
            "inventory_write_attempt",
            {"operation": "create_product", "payload": {"name": "test"}},
        )
    )
    assert structured == {
        "error_code": "INVENTORY_READ_ONLY",
        "message": "Inventory is read-only through this MCP server.",
    }


def test_tool_audit_never_records_access_tokens_or_payloads(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="mcps.server")
    token = "dummy-secret-token-for-test"
    auth = SimpleNamespace(auth_info=SimpleNamespace(
        token=token,
        client_id="test-client",
        subject="test-subject",
        scopes=["inventory:read"],
    ))
    monkeypatch.setattr("mcps.backend.requests.request", Mock())
    asyncio.run(create_mcp_server(auth).call_tool(
        "inventory_write_attempt",
        {"operation": "delete_product", "payload": {"private": "test payload"}},
    ))

    messages = "\n".join(
        record.getMessage() for record in caplog.records
        if record.name == "mcps.server"
    )
    assert "dummy-secret-token-for-test" not in messages
    assert "private" not in messages
    record = next(
        item for item in caplog.records
        if item.name == "mcps.server" and item.getMessage() == "MCP tool invocation"
    )
    assert record.client_id == "test-client"
    assert record.result == "denied"
    assert record.error_code == "INVENTORY_READ_ONLY"


def test_missing_tool_scope_is_rejected_with_http_403():
    auth = SimpleNamespace(auth_info=SimpleNamespace(
        client_id="reader",
        subject="reader",
        scopes=["incidents:read"],
    ))
    downstream = Mock()
    middleware = ToolScopeMiddleware(downstream, auth)
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "incidents_create", "arguments": {}},
    }).encode()
    events = iter([{
        "type": "http.request",
        "body": body,
        "more_body": False,
    }])
    sent = []

    async def receive():
        return next(events)

    async def send(message):
        sent.append(message)

    asyncio.run(middleware({
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [],
    }, receive, send))

    assert sent[0]["status"] == 403
    response_body = json.loads(sent[1]["body"])
    assert response_body["error_code"] == "INSUFFICIENT_SCOPE"
    downstream.assert_not_called()


def test_unhandled_tool_call_is_audited_as_invalid_input(caplog):
    caplog.set_level(logging.INFO, logger="mcps.server")
    auth = SimpleNamespace(auth_info=SimpleNamespace(
        client_id="reader",
        subject="reader",
        scopes=["incidents:read"],
    ))

    async def downstream(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = ToolScopeMiddleware(downstream, auth)
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "incidents_get", "arguments": {"unexpected": True}},
    }).encode()
    events = iter([{
        "type": "http.request",
        "body": body,
        "more_body": False,
    }])

    async def receive():
        return next(events)

    async def send(_message):
        return None

    asyncio.run(middleware({
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [],
    }, receive, send))

    record = next(
        item for item in caplog.records
        if item.name == "mcps.server" and item.getMessage() == "MCP tool invocation"
    )
    assert record.tool_name == "incidents_get"
    assert record.result == "error"
    assert record.error_code == "INVALID_INPUT"


def test_metadata_route_is_publicly_discoverable():
    route = _resource_metadata_route(
        "https://mcp.example.test/mcp",
        "https://issuer.example.test",
    )

    assert route.path == "/.well-known/oauth-protected-resource/mcp"
    assert route.methods == {"GET", "HEAD"}


def asgi_request(app, path, *, method="GET", authorization=None, body=b""):
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("test-client", 1234),
        "server": ("test-server", 8000),
    }
    incoming = iter([{
        "type": "http.request",
        "body": body,
        "more_body": False,
    }])
    sent = []

    async def receive():
        try:
            return next(incoming)
        except StopIteration:
            return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def oauth_test_app():
    issuer = "https://issuer.example.test"
    resource = "https://mcp.example.test/mcp"
    server = MCPAuth(server=AuthServerConfig(
        type=AuthServerType.OIDC,
        metadata=AuthorizationServerMetadata(
            issuer=issuer,
            authorization_endpoint=f"{issuer}/authorize",
            token_endpoint=f"{issuer}/token",
            jwks_uri=f"{issuer}/jwks",
            response_types_supported=["code"],
            code_challenge_methods_supported=["S256"],
        ),
    ))

    def verify(token):
        if token != "valid-test-token":
            raise MCPAuthBearerAuthException(BearerAuthExceptionCode.INVALID_TOKEN)
        return AuthInfo(
            token=token,
            issuer=issuer,
            subject="test-subject",
            client_id="test-client",
            audience=resource,
            scopes=["incidents:read"],
            claims={},
        )

    return build_app(server, resource, issuer, token_verifier=verify)


def test_mcp_initialization_and_tool_calls_require_auth_and_scope():
    app = oauth_test_app()
    list_request = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list",
    }).encode()
    unauthenticated = asgi_request(
        app, "/mcp", method="POST", body=list_request,
    )
    assert unauthenticated[0]["status"] == 401

    invalid_token = asgi_request(
        app, "/mcp", method="POST",
        authorization="Bearer invalid",
        body=list_request,
    )
    assert invalid_token[0]["status"] == 401

    write_request = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "incidents_create", "arguments": {}},
    }).encode()
    insufficient_scope = asgi_request(
        app, "/mcp", method="POST",
        authorization="Bearer valid-test-token",
        body=write_request,
    )
    assert insufficient_scope[0]["status"] == 403
    assert json.loads(insufficient_scope[1]["body"])["error_code"] == "INSUFFICIENT_SCOPE"


def test_metadata_and_readiness_are_public_but_expose_no_tools():
    app = oauth_test_app()
    metadata = asgi_request(
        app, "/.well-known/oauth-protected-resource/mcp",
    )
    assert metadata[0]["status"] == 200
    details = json.loads(metadata[1]["body"])
    assert details["authorization_servers"] == ["https://issuer.example.test"]
    assert set(details["scopes_supported"]) == set(SUPPORTED_SCOPES)

    readiness = asgi_request(app, "/health/ready")
    assert readiness[0]["status"] == 200
    assert json.loads(readiness[1]["body"]) == {"status": "ready"}
