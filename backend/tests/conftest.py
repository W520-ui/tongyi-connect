from tests import isolation  # noqa: F401 -- isolate database before importing the app

# isort: split

from contextlib import ExitStack
from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.agent.commands import CommandRouter
from app.agent.config import AgentSettings
from app.agent.engine import AgentEngine, get_agent_engine
from app.agent.hooks import Hooks
from app.agent.registry import create_default_registry
from app.agent.session import SessionStore
from app.core.config import get_settings
from app.services.workflow import WorkflowMetrics
from tests.support import Runtime, ScriptedProvider


@pytest.fixture(autouse=True)
def temporary_database_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "default.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def runtime_factory(tmp_path, monkeypatch):
    identifiers = count()
    with ExitStack() as resources:

        def create(provider=None):
            provider = provider if provider is not None else ScriptedProvider()
            root = tmp_path / f"runtime-{next(identifiers)}"
            store = SessionStore(root / "sessions.db")
            metrics = WorkflowMetrics(root / "workflow.db")
            resources.callback(metrics.close)
            resources.callback(store.close)
            engine = AgentEngine(
                settings=AgentSettings(
                    _env_file=None,
                    llm_api_key="test-key",
                    llm_base_url="https://example.test/v1",
                    llm_model="test-model",
                    llm_timeout_seconds=1,
                    max_tool_rounds=4,
                    session_ttl_hours=24,
                    max_history_turns=10,
                ),
                provider=provider,
                registry=create_default_registry(),
                store=store,
                commands=CommandRouter(store),
                hooks=Hooks(),
            )
            monkeypatch.setattr("app.agent.engine.metrics", metrics)
            return Runtime(engine, metrics, provider)

        yield create


@pytest.fixture
def api_client(runtime_factory, monkeypatch):
    from app import main

    runtime = runtime_factory()
    monkeypatch.setattr("app.api.v1.endpoints.agent.metrics", runtime.metrics)
    monkeypatch.setattr("app.api.v1.endpoints.workflow.metrics", runtime.metrics)
    main.app.dependency_overrides[get_agent_engine] = lambda: runtime.engine
    try:
        # Phase 0 keeps the module-level lifecycle; avoid closing shared globals.
        # Lifespan resource creation and teardown will be covered in phase 1.
        with TestClient(main.app, raise_server_exceptions=True) as client:
            monkeypatch.setattr(main, "metrics", _AlreadyManagedResource())
            monkeypatch.setattr(main, "get_agent_engine", _AlreadyManagedResource)
            yield client, runtime
    finally:
        main.app.dependency_overrides.clear()


class _AlreadyManagedResource:
    def close(self):
        pass
