"""Gives every request an id, makes it visible to every log line, puts it on the response and writes one access line."""
from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.request_context import request_id_var

log = logging.getLogger("classtasks.access")
HEADER = "X-Request-ID"
_SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def pick_request_id(incoming: str | None) -> str:
    """Keep the caller's id only if it is short and made of safe characters (it goes into logs); otherwise make a new one."""
    if incoming and _SAFE_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = pick_request_id(Headers(scope=scope).get(HEADER))
        scope.setdefault("state", {})["request_id"] = rid
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = {"code": None}

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                MutableHeaders(scope=message)[HEADER] = rid
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            status["code"] = 500
            raise
        finally:
            log.info(
                "request finished",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],  # no query string: it can hold secrets
                    "status": status["code"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id_var.reset(token)
