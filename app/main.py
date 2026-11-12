"""The one place that knows every layer and wires them together (the 'composition root')."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Callable, TextIO

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.middleware import RequestIdMiddleware
from app.api.routes import build_router
from app.logging_setup import configure_logging
from app.repositories.sqlite import SqliteTaskRepository
from app.services.ports import TaskRepository
from app.services.tasks import TaskService
from app.settings import Settings, StartupError


def create_app(
    settings: Settings | None = None,
    *,
    log_stream: TextIO | None = None,
    repository: TaskRepository | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    settings = settings or Settings.load()  # raises SettingsError right here if anything is wrong
    configure_logging(settings.log_level, log_stream)
    if repository is None:
        sqlite_repo = SqliteTaskRepository(settings.database_path)
        try:
            sqlite_repo.init_schema()
        except sqlite3.Error as error:
            raise StartupError(f"Cannot open the database at {settings.database_path!r}: {error}") from None
        repository = sqlite_repo
    service = TaskService(repository, settings.max_title_length, **({"clock": clock} if clock else {}))
    app = FastAPI(title="Class Tasks API", version="1.0.0")
    app.state.service = service
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(build_router())
    return app
