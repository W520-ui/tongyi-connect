from pathlib import Path

from app.agent.session import SessionStore
from app.core.config import Settings
from app.services.workflow import WorkflowMetrics


def test_default_database_still_points_to_backend_data(monkeypatch):
    monkeypatch.delenv("WORKFLOW_DB_PATH")
    settings = Settings(_env_file=None)
    expected = Path(__file__).resolve().parents[1] / "data" / "workflow.db"
    assert settings.workflow_db_path == expected


def test_relative_database_configuration_is_anchored_to_backend():
    settings = Settings(_env_file=None, workflow_db_path="local/demo.db")
    expected = Path(__file__).resolve().parents[1] / "local" / "demo.db"
    assert settings.workflow_db_path == expected


def test_both_default_stores_use_the_temporary_environment(tmp_path):
    store = SessionStore()
    metrics = WorkflowMetrics()
    try:
        assert store.db_path == metrics.db_path == tmp_path / "default.db"
        assert store.connection.execute("PRAGMA database_list").fetchone()[2] == str(store.db_path)
        assert metrics.snapshot()["total_conversations"] == 0
    finally:
        store.close()
        metrics.close()
