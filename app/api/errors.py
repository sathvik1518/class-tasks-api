"""Every error answer is made HERE. This is the only file that knows which rule error means which status code.
Routes just let the error rise; this file turns it into the same JSON shape every time."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import DuplicateTitle, InvalidTitle, TaskError, TaskNotFound

log = logging.getLogger("classtasks.api")

# The ONE table. A new domain error without a line here is a test failure (tests/test_errors.py).
STATUS_FOR_ERROR: dict[type[TaskError], int] = {
    InvalidTitle: 422,
    DuplicateTitle: 409,
    TaskNotFound: 404,
}

_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _body(request: Request, code: str, message: str, **extra: object) -> dict:
    return {"error": {"code": code, "message": message, "request_id": _request_id(request), **extra}}


def _status_for(error: TaskError) -> int | None:
    for cls in type(error).__mro__:
        if cls in STATUS_FOR_ERROR:
            return STATUS_FOR_ERROR[cls]
    return None


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TaskError)
    async def on_task_error(request: Request, error: TaskError):
        status = _status_for(error)
        if status is None:  # a new error nobody mapped: say so loudly, answer safely
            log.error("domain error has no status code", extra={"error_type": type(error).__name__})
            return await on_unexpected(request, error)
        return JSONResponse(_body(request, error.code, error.message), status_code=status)

    @app.exception_handler(RequestValidationError)
    async def on_invalid_request(request: Request, error: RequestValidationError):
        fields = []
        for item in error.errors():
            loc = item.get("loc", ())
            field = "body" if item.get("type") == "json_invalid" else (".".join(str(p) for p in loc[1:]) or str(loc[0] if loc else "request"))
            fields.append({"field": field, "problem": item.get("msg", "Invalid value.")})  # never echo the value back
        return JSONResponse(_body(request, "invalid_request", "The request is not valid.", fields=fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def on_http_error(request: Request, error: StarletteHTTPException):
        code = _HTTP_CODES.get(error.status_code, "http_error")
        message = {404: "There is no such address.", 405: "That method is not allowed here."}.get(error.status_code, "The request could not be served.")
        return JSONResponse(_body(request, code, message), status_code=error.status_code, headers=error.headers)

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, error: Exception):
        rid = _request_id(request)
        # Runs outside the request-id middleware, so the id is passed by hand (and put on the response by hand).
        log.error("unhandled error", exc_info=(type(error), error, error.__traceback__), extra={"request_id": rid})
        body = _body(request, "internal_error", "Something went wrong on our side. Quote the request id if you ask for help.")
        return JSONResponse(body, status_code=500, headers={"X-Request-ID": rid} if rid else None)
