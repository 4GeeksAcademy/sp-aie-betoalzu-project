import ast
import os
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.testclient import TestClient

SERVER_PATH = Path(__file__).resolve().parents[2] / "server.py"


@pytest.fixture
def static_client(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    monkeypatch.chdir(root)
    app = FastAPI()
    namespace = {
        "app": app,
        "os": os,
        "subprocess": subprocess,
        "static_file_dir": str(root),
        "FileResponse": FileResponse,
        "HTMLResponse": HTMLResponse,
    }
    # Isolate the actual routes from unrelated startup/database integrations.
    tree = ast.parse(SERVER_PATH.read_text())
    routes = [
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name in {"serve_dir_directory_index", "serve_any_other_file"}
    ]
    assert any(node.name == "serve_dir_directory_index" for node in routes)
    exec(compile(ast.Module(body=routes, type_ignores=[]), str(SERVER_PATH), "exec"), namespace)
    with TestClient(app) as client:
        yield client, root


@pytest.mark.parametrize("filename", [
    ".env",
    "server.py",
    "data_project/users_db.json",
    "private/index.html",
])
def test_internal_files_are_not_public(static_client, filename):
    client, root = static_client
    target = root / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SYNTHETIC_AUDIT_CANARY")

    response = client.get(f"/{filename}")

    assert response.status_code == 404
    assert "SYNTHETIC_AUDIT_CANARY" not in response.text


def test_encoded_traversal_is_not_public(static_client):
    client, root = static_client
    (root.parent / "outside-canary.txt").write_text("SYNTHETIC_OUTSIDE_CANARY")

    response = client.get("/..%2Foutside-canary.txt")

    assert response.status_code == 404
    assert "SYNTHETIC_OUTSIDE_CANARY" not in response.text


def test_symlink_is_not_public(static_client):
    client, root = static_client
    outside = root.parent / "outside-canary.txt"
    outside.write_text("SYNTHETIC_OUTSIDE_CANARY")
    (root / "linked.txt").symlink_to(outside)

    response = client.get("/linked.txt")

    assert response.status_code == 404
    assert "SYNTHETIC_OUTSIDE_CANARY" not in response.text


def test_root_index_is_preserved(static_client):
    client, root = static_client
    (root / "index.html").write_text("<h1>Synthetic public index</h1>")

    response = client.get("/")

    assert response.status_code == 200
    assert "Synthetic public index" in response.text
