from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RequestHandoff:
    reason_code: Literal["after_sales", "user_request", "guardrail"]
    reason_text: str
    issue_summary: str | None = None


@dataclass(frozen=True)
class FocusProducts:
    product_ids: tuple[str, ...]


@dataclass(frozen=True)
class UpdateSlots:
    destination_country: str | None = None
    quantity: int | None = None


Effect = RequestHandoff | FocusProducts | UpdateSlots
