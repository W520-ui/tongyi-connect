import ast
import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.scripts.export_openapi import export_openapi
from tests.support import ScriptedProvider

APP_ROOT = Path(__file__).absolute().parents[1] / "app"


def test_lifespan_creates_and_closes_owned_resources(settings_factory):
    app = create_app(settings_factory(), llm_client=ScriptedProvider())
    assert app.state._state == {}
    with TestClient(app) as client:
        state = app.state
        assert not state.http_client.is_closed
        assert client.portal.call(state.database.ping)
        assert state.conversation_service.runner.client is state.llm
        assert client.get("/api/v1/status").json()["data"] == {
            "version": "0.1.0",
            "llm_configured": True,
            "model": "test-model",
            "db_ok": True,
        }
    assert state.http_client.is_closed
    assert state.database.closed
    assert not asyncio.run(state.database.ping())
    assert not state.background.tasks


def test_startup_failure_closes_resources_already_created(settings_factory, monkeypatch):
    clients, databases = [], []
    from app.main import Database, httpx

    original_client = httpx.AsyncClient

    def capture_client(*args, **kwargs):
        client = original_client(*args, **kwargs)
        clients.append(client)
        return client

    def capture_database(url):
        database = Database(url)
        databases.append(database)
        return database

    async def fail_seed(_database):
        raise RuntimeError("Startup failed")

    monkeypatch.setattr("app.main.httpx.AsyncClient", capture_client)
    monkeypatch.setattr("app.main.Database", capture_database)
    monkeypatch.setattr("app.main.seed_missing", fail_seed)
    with (
        pytest.raises(RuntimeError, match="Startup failed"),
        TestClient(create_app(settings_factory())),
    ):
        pytest.fail("Failed startup must not serve requests")
    assert len(clients) == len(databases) == 1
    assert clients[0].is_closed and databases[0].closed


def test_status_without_model_and_health_compatibility(settings_factory):
    app = create_app(settings_factory(llm_api_key=None))
    with TestClient(app) as client:
        assert client.get("/api/v1/status").json()["data"]["model"] is None
        assert client.get("/api/v1/status").json()["data"]["llm_configured"] is False
        assert client.get("/api/v1/health").json()["service"] == "tongyi-connect-api"


def test_separate_app_instances_do_not_share_engine_or_database(settings_factory):
    first = create_app(settings_factory(), llm_client=ScriptedProvider())
    second = create_app(settings_factory(), llm_client=ScriptedProvider())
    with TestClient(first), TestClient(second):
        assert first.state.conversation_service is not second.state.conversation_service
        assert first.state.database.path != second.state.database.path
        assert first.state.http_client is not second.state.http_client


def test_all_modules_import_without_constructing_resources(tmp_path):
    script = """
import importlib, pkgutil, sqlite3, httpx, pydantic_settings, sqlalchemy.ext.asyncio
def forbidden(*args, **kwargs):
    raise AssertionError('Application import constructed a resource')
sqlite3.connect = forbidden
sqlalchemy.ext.asyncio.create_async_engine = forbidden
httpx.AsyncClient.__init__ = forbidden
pydantic_settings.BaseSettings.__init__ = forbidden
import app
for entry in pkgutil.walk_packages(app.__path__, app.__name__ + '.'):
    importlib.import_module(entry.name)
import app.main
assert app.main.app.application is None
print('All application modules imported without resource construction')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=APP_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "without resource construction" in result.stdout


def test_import_dependencies_obey_layer_contracts():
    allowed = {
        "api": {"api", "services", "domain", "core"},
        "services": {"services", "agent", "repositories", "domain", "core"},
        "agent": {"agent", "domain", "core"},
        "repositories": {"repositories", "domain", "core"},
        "domain": {"domain"},
        "core": {"core", "domain"},
    }
    violations = []
    for path in APP_ROOT.rglob("*.py"):
        parts = path.relative_to(APP_ROOT).parts
        layer = parts[0]
        if layer not in allowed:
            continue
        module_name = "app." + ".".join(path.relative_to(APP_ROOT).with_suffix("").parts)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = module_name.rsplit(".", 1)[0]
                    target = importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package
                    )
                else:
                    target = node.module or ""
                targets = [target]
                if target == "app":
                    targets = ["app." + alias.name for alias in node.names]
            for target in targets:
                if target.startswith("app.") and target.split(".")[1] not in allowed[layer]:
                    violations.append(f"{path.relative_to(APP_ROOT)}:{node.lineno} -> {target}")
    assert violations == []


def test_http_pydantic_models_live_only_in_api_schemas():
    violations = []
    for path in APP_ROOT.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "BaseModel" for base in node.bases
            ):
                relative = path.relative_to(APP_ROOT).as_posix()
                if not relative.startswith("api/v1/schemas/") and not (
                    relative.startswith("agent/tools/") and node.name.endswith("Args")
                ):
                    violations.append(relative + ":" + node.name)
    assert not violations


def test_openapi_export_does_not_start_resources(tmp_path, settings_factory, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Export must not start resources")

    monkeypatch.setattr("app.main.Database", forbidden)
    monkeypatch.setattr("app.main.httpx.AsyncClient", forbidden)
    target = export_openapi(tmp_path / "openapi.json", settings_factory())
    schema = json.loads(target.read_text(encoding="utf-8"))
    assert "/api/v1/status" in schema["paths"]
    assert "/api/v1/agent/chat" in schema["paths"]
    workflow = schema["components"]["schemas"]["LegacyAgentWorkflowData"]
    assert "session_id" in workflow["properties"]
    assert "trace" in workflow["properties"]
    assert "test-key" not in target.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.db"))


def test_env_file_is_anchored_to_backend(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert Path(Settings.model_config["env_file"]) == APP_ROOT.parent / ".env"
