import logging

from fastapi.responses import JSONResponse

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def error_response(error: AppError):
    return JSONResponse(
        status_code=error.status_code,
        content={
            "status": "error",
            "detail": error.message,
            "error": {"code": error.code, "message": error.message, "details": error.details},
        },
    )


class SafeErrorsMiddleware:
    """Keep unexpected tracebacks out of HTTP responses, including debug mode."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def track(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track)
        except Exception:
            if started:
                raise
            logger.exception("Unexpected HTTP failure")
            await error_response(AppError("INTERNAL_ERROR"))(scope, receive, send)
