from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

logger = logging.getLogger(__name__)

Hook = Callable[[str, dict[str, Any]], None]


class Hooks:
    """Tiny event bus so archiving, logging and dashboards stay decoupled."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Hook]] = {}

    def on(self, event: str, handler: Hook) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        for handler in self._handlers.get(event, []):
            try:
                handler(event, payload)
            except Exception:
                logger.exception("agent hook failed for %s", event)
