"""Redirect import-time resources before loading any application module."""

import atexit
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_import_directory = tempfile.TemporaryDirectory(prefix="tongyi-test-import-")
os.environ["WORKFLOW_DB_PATH"] = str(Path(_import_directory.name) / "workflow.db")


def _close_import_resources() -> None:
    module = sys.modules.get("app.services.workflow")
    if module is not None:
        try:
            module.metrics.close()
        except sqlite3.ProgrammingError:
            pass
    _import_directory.cleanup()


atexit.register(_close_import_resources)
