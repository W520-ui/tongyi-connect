"""Service notifications independent of the HTTP transport."""

from dataclasses import dataclass

from app.agent.events import TextDelta as TextDelta
from app.agent.events import ToolFinished as ToolFinished
from app.agent.events import ToolStarted as ToolStarted
from app.domain.types import WorkflowResult


@dataclass(frozen=True)
class WorkflowCompleted:
    result: WorkflowResult


@dataclass(frozen=True)
class AnalysisCompleted:
    result: WorkflowResult
    outcome: dict
