from contextlib import ExitStack
from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.catalog import CatalogService
from tests.support import Runtime, ScriptedProvider


@pytest.fixture(autouse=True)
def temporary_database_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "default.db"))


@pytest.fixture
def catalog():
    return CatalogService.load_seed()


@pytest.fixture
def settings_factory(tmp_path):
    identifiers = count()

    def create(**overrides):
        values = {
            "_env_file": None,
            "workflow_db_path": tmp_path / f"runtime-{next(identifiers)}.db",
            "llm_api_key": "test-key",
            "llm_base_url": "https://example.test/v1",
            "llm_model": "test-model",
            "llm_timeout_seconds": 1,
            "max_tool_rounds": 4,
            "session_ttl_hours": 24,
            "max_history_turns": 10,
            "debug": False,
        }
        return Settings(**{**values, **overrides})

    return create


@pytest.fixture
def runtime_factory(settings_factory):
    with ExitStack() as resources:

        def create(provider=None, **overrides):
            provider = provider if provider is not None else ScriptedProvider()
            application = create_app(settings_factory(**overrides), llm_client=provider)
            client = resources.enter_context(TestClient(application, raise_server_exceptions=True))
            state = application.state
            runtime = Runtime(
                state.conversation_service, state.analytics, state.archive, state.handoffs, provider
            )
            runtime.client, runtime.app = client, application
            return runtime

        yield create


@pytest.fixture
def api_client(runtime_factory):
    runtime = runtime_factory()
    return runtime.client, runtime
