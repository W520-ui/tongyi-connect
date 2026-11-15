from contextlib import ExitStack
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.types import Product
from app.main import create_app
from app.repositories.seed import seed_values
from tests.support import Runtime, ScriptedProvider


@pytest.fixture(autouse=True)
def temporary_database_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///" + str(tmp_path / "default.db"))


@pytest.fixture
def catalog():
    products, _rules = seed_values()
    return SimpleNamespace(
        products=tuple(Product(**{**item, "aliases": tuple(item["aliases"])}) for item in products)
    )


@pytest.fixture
def settings_factory(tmp_path):
    identifiers = count()

    def create(**overrides):
        values = {
            "_env_file": None,
            "database_url": "sqlite+aiosqlite:///"
            + str(tmp_path / f"runtime-{next(identifiers)}.db"),
            "llm_api_key": "test-key",
            "llm_base_url": "https://example.test/v1",
            "llm_model": "test-model",
            "llm_timeout_seconds": 1,
            "max_tool_rounds": 4,
            "analysis_enabled": False,
            "debug": False,
        }
        return Settings(**{**values, **overrides})

    return create


@pytest.fixture
def runtime_factory(settings_factory):
    with ExitStack() as resources:

        def create(provider=None, analysis_provider=None, **overrides):
            provider = provider if provider is not None else ScriptedProvider()
            application = create_app(
                settings_factory(**overrides),
                llm_client=provider,
                analysis_client=analysis_provider,
            )
            client = resources.enter_context(TestClient(application, raise_server_exceptions=True))
            state = application.state
            return Runtime(
                state.conversation_service,
                state.analytics,
                state.database,
                state.handoffs,
                provider,
                client,
                application,
            )

        yield create


@pytest.fixture
def api_client(runtime_factory):
    runtime = runtime_factory()
    return runtime.client, runtime
