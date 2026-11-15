from typing import Literal

from pydantic import BaseModel

from app.core.errors import ERRORS


class ValidationDetail(BaseModel):
    loc: list[str | int]
    msg: str


class ErrorData(BaseModel):
    code: str
    message: str
    details: list[ValidationDetail] | None


class ErrorEnvelope(BaseModel):
    status: Literal["error"] = "error"
    error: ErrorData
    detail: str


ERROR_RESPONSES = {status: {"model": ErrorEnvelope} for status, _message in ERRORS.values()}
