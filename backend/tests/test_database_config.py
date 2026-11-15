from pathlib import Path

from app.core.config import Settings
from app.repositories.archive import WorkflowArchive
from app.repositories.session import SessionStore


def test_default_database_still_points_to_backend_data(monkeypatch):
    monkeypatch.delenv("WORKFLOW_DB_PATH")
    settings = Settings(_env_file=None)
    assert (
        settings.workflow_db_path == Path(__file__).absolute().parents[1] / "data" / "workflow.db"
    )


def test_relative_database_configuration_is_anchored_to_backend():
    settings = Settings(_env_file=None, workflow_db_path="local/demo.db")
    assert settings.workflow_db_path == Path(__file__).absolute().parents[1] / "local" / "demo.db"


def test_both_stores_use_the_temporary_configuration(tmp_path):
    settings = Settings(_env_file=None)
    store = SessionStore(settings.workflow_db_path)
    archive = WorkflowArchive(settings.workflow_db_path)
    try:
        assert store.db_path == archive.db_path == tmp_path / "default.db"
        assert store.connection.execute("PRAGMA database_list").fetchone()[2] == str(store.db_path)
        assert archive.aggregates()["total"] == 0
    finally:
        store.close()
        archive.close()
