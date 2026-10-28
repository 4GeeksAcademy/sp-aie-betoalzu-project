from __future__ import annotations

import json
import logging
import os
from collections import Counter
from collections.abc import Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcpauth import MCPAuth
from mcpauth.config import AuthServerType
from mcpauth.utils import fetch_server_config
from pydantic import Field, ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcps.backend import (
    BackendFailure,
    IncidentCreateInput,
    IncidentGetInput,
    IncidentTransitionInput,
    IncidentUpdateInput,
    InventoryGetInput,
    InventoryOperation,
    InventoryWriteInput,
    create_incident,
    get_incidents,
    get_products,
    transition_incident,
    update_incident,
)
from services.api.incidents.models import (
    IncidentBranch,
    IncidentCategory,
    IncidentOrigin,
    IncidentStatus,
)

logger = logging.getLogger(__name__)
SUPPORTED_SCOPES = ("incidents:read", "incidents:write", "inventory:read")
TOOL_SCOPES = {
    "incidents_create": "incidents:write",
    "incidents_get": "incidents:read",
    "incidents_update": "incidents:write",
    "incidents_transition_status": "incidents:write",
    "inventory_get_products": "inventory:read",
    "inventory_write_attempt": "inventory:read",
}
_request_audit_id: ContextVar[str | None] = ContextVar(
    "mcp_request_audit_id", default=None,
)
_tool_audit_counts: ContextVar[dict[str, int] | None] = ContextVar(
    "mcp_tool_audit_counts", default=None,
)


def _validated_url(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} must be an HTTP(S) URL without credentials, query, or fragment.")
    return value.rstrip("/")


def create_auth() -> tuple[MCPAuth, str, str]:
    issuer = _validated_url(os.getenv("MCP_AUTH_ISSUER", "").strip(), "MCP_AUTH_ISSUER")
    resource = _validated_url(
        os.getenv("MCP_RESOURCE_URI", "").strip(),
        "MCP_RESOURCE_URI",
    )
    auth_type_value = os.getenv("MCP_AUTH_TYPE", "oidc").strip().lower()
    auth_types = {
        "oidc": AuthServerType.OIDC,
        "oauth": AuthServerType.OAUTH,
    }
    try:
        auth_type = auth_types[auth_type_value]
    except KeyError as exc:
        raise ValueError("MCP_AUTH_TYPE must be either 'oidc' or 'oauth'.") from exc

    auth_server = fetch_server_config(issuer, auth_type)
    return MCPAuth(server=auth_server), resource, issuer


def _resource_metadata_route(resource: str, issuer: str) -> Route:
    resource_path = urlsplit(resource).path.rstrip("/")
    metadata_path = "/.well-known/oauth-protected-resource"
    if resource_path:
        metadata_path += resource_path

    async def metadata(_request: Request) -> JSONResponse:
        return JSONResponse({
            "resource": resource,
            "authorization_servers": [issuer],
            "scopes_supported": list(SUPPORTED_SCOPES),
            "bearer_methods_supported": ["header"],
        })

    return Route(metadata_path, metadata, methods=["GET"])


def _client_identity(auth: MCPAuth) -> str:
    auth_info = auth.auth_info
    if auth_info is None:
        return "unknown"
    return auth_info.client_id or auth_info.subject


def _record_invocation(
    auth: MCPAuth,
    *,
    tool_name: str,
    result: str,
    error_code: str | None = None,
    request_id: str | None = None,
) -> None:
    counts = _tool_audit_counts.get()
    if counts is not None:
        counts[tool_name] = counts.get(tool_name, 0) + 1
    logger.info(
        "MCP tool invocation",
        extra={
            "tool_name": tool_name,
            "client_id": _client_identity(auth),
            "result": result,
            "error_code": error_code,
            "request_id": request_id or _request_audit_id.get() or str(uuid4()),
        },
    )


def _error(code: str, message: str) -> dict[str, str]:
    return {"error_code": code, "message": message}


def _run_tool(
    auth: MCPAuth,
    *,
    tool_name: str,
    required_scope: str,
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    request_id = _request_audit_id.get() or str(uuid4())
    auth_info = auth.auth_info
    if auth_info is None:
        code = "AUTHENTICATION_REQUIRED"
        _record_invocation(
            auth, tool_name=tool_name, result="denied",
            error_code=code, request_id=request_id,
        )
        return _error(code, "A valid bearer token is required.")
    if required_scope not in auth_info.scopes:
        code = "INSUFFICIENT_SCOPE"
        _record_invocation(
            auth, tool_name=tool_name, result="denied",
            error_code=code, request_id=request_id,
        )
        return _error(code, f"The '{required_scope}' scope is required.")

    try:
        result = operation()
    except ValidationError:
        result = _error("INVALID_INPUT", "Tool arguments are invalid.")
    except BackendFailure as exc:
        result = _error(exc.code, exc.message)

    code = result.get("error_code")
    outcome = (
        "denied" if code == "INVENTORY_READ_ONLY"
        else "error" if code
        else "success"
    )
    _record_invocation(
        auth, tool_name=tool_name, result=outcome,
        error_code=code, request_id=request_id,
    )
    return result


class ToolScopeMiddleware:
    def __init__(self, app, auth: MCPAuth) -> None:
        self.app = app
        self.auth = auth

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        messages: list[dict[str, Any]] = []
        body = bytearray()
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            body.extend(message.get("body", b""))
            if len(body) > 1_000_000:
                response = JSONResponse(
                    {"error_code": "INVALID_INPUT", "message": "Request body is too large."},
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        try:
            request_payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            request_payload = None

        calls = request_payload if isinstance(request_payload, list) else [request_payload]
        tool_calls: list[str] = []
        denied_calls: list[tuple[str, str, str]] = []
        for call in calls:
            if not isinstance(call, dict) or call.get("method") != "tools/call":
                continue
            params = call.get("params")
            name = params.get("name") if isinstance(params, dict) else None
            tool_name = name if isinstance(name, str) else "unknown_tool"
            tool_calls.append(tool_name)
            required_scope = TOOL_SCOPES.get(tool_name)
            if required_scope is None:
                continue
            auth_info = self.auth.auth_info
            if auth_info is None:
                denied_calls.append((tool_name, "AUTHENTICATION_REQUIRED", required_scope))
            elif required_scope not in auth_info.scopes:
                denied_calls.append((tool_name, "INSUFFICIENT_SCOPE", required_scope))

        if denied_calls:
            request_id = str(uuid4())
            for tool_name, error_code, _scope_name in denied_calls:
                _record_invocation(
                    self.auth,
                    tool_name=tool_name,
                    result="denied",
                    error_code=error_code,
                    request_id=request_id,
                )
            error_code, required_scope = denied_calls[0][1:]
            response = JSONResponse(
                {
                    "error_code": error_code,
                    "message": (
                        f"The '{required_scope}' scope is required."
                        if error_code == "INSUFFICIENT_SCOPE"
                        else "A valid bearer token is required."
                    ),
                    "request_id": request_id,
                },
                status_code=403 if error_code == "INSUFFICIENT_SCOPE" else 401,
            )
            await response(scope, receive, send)
            return

        replay = iter(messages)

        async def replay_receive():
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        request_id = str(uuid4())
        request_token = _request_audit_id.set(request_id)
        counts: dict[str, int] = {}
        counts_token = _tool_audit_counts.set(counts)
        try:
            await self.app(scope, replay_receive, send)
        finally:
            for tool_name, total in Counter(tool_calls).items():
                unlogged = total - counts.get(tool_name, 0)
                for _ in range(max(unlogged, 0)):
                    _record_invocation(
                        self.auth,
                        tool_name=tool_name,
                        result="error",
                        error_code="INVALID_INPUT",
                        request_id=request_id,
                    )
            _tool_audit_counts.reset(counts_token)
            _request_audit_id.reset(request_token)


class AuthenticationAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        if response.status_code == 401:
            has_bearer = bool(request.headers.get("authorization"))
            logger.warning(
                "MCP authentication rejected",
                extra={
                    "tool_name": None,
                    "client_id": None,
                    "result": "denied",
                    "error_code": (
                        "INVALID_ACCESS_TOKEN" if has_bearer
                        else "AUTHENTICATION_REQUIRED"
                    ),
                    "request_id": str(uuid4()),
                },
            )
        return response


def create_mcp_server(auth: MCPAuth) -> FastMCP:
    mcp = FastMCP("Nexova Business Tools", stateless_http=True)

    @mcp.tool()
    def incidents_create(
        title: Annotated[str, Field(min_length=1, max_length=120, description="Título (1-120 caracteres).")],
        category: Annotated[IncidentCategory, Field(description="Categoría de dominio permitida.")],
        origin: Annotated[IncidentOrigin, Field(description="Origen: customer, branch o internal.")],
        description: Annotated[str | None, Field(description="Descripción detallada.")] = None,
        branch: Annotated[IncidentBranch, Field(description="Sede; por defecto central.")] = IncidentBranch.CENTRAL,
        reported_by: Annotated[str | None, Field(max_length=255, description="Persona que reporta.")] = None,
        assigned_to: Annotated[str | None, Field(max_length=255, description="Persona asignada.")] = None,
        ticket_id: Annotated[str | None, Field(max_length=50, description="Identificador externo del ticket.")] = None,
    ) -> dict[str, Any]:
        """Crear una incidencia; requiere incidents:write.

        Devuelve la incidencia creada con ID, estado, campos de dominio y fechas.
        El estado inicial lo asigna el backend como open. Los errores incluyen
        error_code y message.
        """
        def operation() -> dict[str, Any]:
            incident = create_incident(IncidentCreateInput(
                title=title, category=category, origin=origin, description=description,
                branch=branch, reported_by=reported_by, assigned_to=assigned_to,
                ticket_id=ticket_id,
            ))
            return incident.model_dump(mode="json")

        return _run_tool(
            auth, tool_name="incidents_create", required_scope="incidents:write",
            operation=operation,
        )

    @mcp.tool()
    def incidents_get(
        incident_id: Annotated[int | None, Field(gt=0, description="ID numérico positivo.")] = None,
        ticket_id: Annotated[str | None, Field(min_length=1, max_length=50, description="Coincidencia exacta del ID externo.")] = None,
        status: Annotated[IncidentStatus | None, Field(description="Filtrar por estado.")] = None,
        category: Annotated[IncidentCategory | None, Field(description="Filtrar por categoría.")] = None,
        branch: Annotated[IncidentBranch | None, Field(description="Filtrar por sede.")] = None,
        origin: Annotated[IncidentOrigin | None, Field(description="Filtrar por origen.")] = None,
    ) -> dict[str, Any]:
        """Consultar incidencias; requiere incidents:read e ID o al menos un filtro.

        Devuelve status (success/not_found) y una lista incidents, incluso para un
        único resultado. Los errores incluyen error_code y message.
        """
        def operation() -> dict[str, Any]:
            items = get_incidents(IncidentGetInput(
                incident_id=incident_id, ticket_id=ticket_id, status=status,
                category=category, branch=branch, origin=origin,
            ))
            return {
                "status": "success" if items else "not_found",
                "incidents": [item.model_dump(mode="json") for item in items],
            }

        return _run_tool(
            auth, tool_name="incidents_get", required_scope="incidents:read",
            operation=operation,
        )

    @mcp.tool()
    def incidents_update(
        incident_id: Annotated[int, Field(gt=0, description="ID numérico positivo.")],
        title: Annotated[str | None, Field(min_length=1, max_length=120, description="Título de 1-120 caracteres.")] = None,
        description: Annotated[str | None, Field(description="Descripción detallada.")] = None,
        category: Annotated[IncidentCategory | None, Field(description="Categoría permitida.")] = None,
        origin: Annotated[IncidentOrigin | None, Field(description="Origen permitido.")] = None,
        branch: Annotated[IncidentBranch | None, Field(description="Sede permitida.")] = None,
        reported_by: Annotated[str | None, Field(max_length=255, description="Persona que reporta.")] = None,
        assigned_to: Annotated[str | None, Field(max_length=255, description="Persona asignada.")] = None,
        ticket_id: Annotated[str | None, Field(max_length=50, description="Identificador externo del ticket.")] = None,
    ) -> dict[str, Any]:
        """Editar campos de una incidencia; requiere incidents:write.

        Devuelve la incidencia actualizada. No acepta status; los errores incluyen
        error_code y message.
        """
        def operation() -> dict[str, Any]:
            changes = {
                key: value
                for key, value in {
                    "title": title,
                    "description": description,
                    "category": category,
                    "origin": origin,
                    "branch": branch,
                    "reported_by": reported_by,
                    "assigned_to": assigned_to,
                    "ticket_id": ticket_id,
                }.items()
                if value is not None
            }
            incident = update_incident(IncidentUpdateInput.model_validate({
                "incident_id": incident_id,
                **changes,
            }))
            return incident.model_dump(mode="json")

        return _run_tool(
            auth, tool_name="incidents_update", required_scope="incidents:write",
            operation=operation,
        )

    @mcp.tool()
    def incidents_transition_status(
        incident_id: Annotated[int, Field(gt=0, description="ID numérico positivo.")],
        status: Annotated[IncidentStatus, Field(description="Estado de destino permitido.")],
    ) -> dict[str, Any]:
        """Cambiar estado mediante PATCH dedicado; requiere incidents:write.

        Devuelve la incidencia actualizada; una transición inválida devuelve
        INVALID_STATUS_TRANSITION. Resolver requiere confirmación humana fuera
        de MCP y devuelve HUMAN_CONFIRMATION_REQUIRED.
        """
        def operation() -> dict[str, Any]:
            incident = transition_incident(IncidentTransitionInput(
                incident_id=incident_id, status=status,
            ))
            return incident.model_dump(mode="json")

        return _run_tool(
            auth, tool_name="incidents_transition_status",
            required_scope="incidents:write", operation=operation,
        )

    @mcp.tool()
    def inventory_get_products(
        product_id: Annotated[int | None, Field(gt=0, description="ID numérico positivo.")] = None,
        search: Annotated[str | None, Field(min_length=1, description="Buscar en nombre o SKU.")] = None,
    ) -> dict[str, Any]:
        """Consultar productos de solo lectura; requiere inventory:read.

        Devuelve status (success/not_found) y products con current_stock. Los
        errores incluyen error_code y message.
        """
        def operation() -> dict[str, Any]:
            products = get_products(InventoryGetInput(product_id=product_id, search=search))
            return {
                "status": "success" if products else "not_found",
                "products": [product.model_dump(mode="json") for product in products],
            }

        return _run_tool(
            auth, tool_name="inventory_get_products", required_scope="inventory:read",
            operation=operation,
        )

    @mcp.tool()
    def inventory_write_attempt(
        operation: Annotated[InventoryOperation, Field(description="Operación de escritura que se intentaría.")],
        payload: Annotated[dict[str, Any] | None, Field(description="Payload opcional; no se procesa ni envía.")] = None,
    ) -> dict[str, Any]:
        """Siempre rechaza escrituras con INVENTORY_READ_ONLY; requiere inventory:read.

        Devuelve error_code y message. No realiza llamadas al backend.
        """
        def reject_write() -> dict[str, Any]:
            InventoryWriteInput(operation=operation, payload=payload)
            return _error(
                "INVENTORY_READ_ONLY",
                "Inventory is read-only through this MCP server.",
            )

        return _run_tool(
            auth, tool_name="inventory_write_attempt", required_scope="inventory:read",
            operation=reject_write,
        )

    return mcp


def build_app(
    auth: MCPAuth,
    resource: str,
    issuer: str,
    *,
    token_verifier: str | Callable[[str], Any] = "jwt",
) -> Starlette:
    mcp = create_mcp_server(auth)

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        async with mcp.session_manager.run():
            yield

    async def readiness(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ready"})

    bearer_auth = Middleware(
        auth.bearer_auth_middleware(token_verifier, audience=resource),
    )
    return Starlette(
        routes=[
            _resource_metadata_route(resource, issuer),
            Route("/health/ready", readiness, methods=["GET"]),
            Mount(
                "/",
                app=ToolScopeMiddleware(mcp.streamable_http_app(), auth),
                middleware=[Middleware(AuthenticationAuditMiddleware), bearer_auth],
            ),
        ],
        lifespan=lifespan,
    )


def create_app() -> Starlette:
    auth, resource, issuer = create_auth()
    return build_app(auth, resource, issuer)


def main() -> None:
    import uvicorn

    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8001"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
