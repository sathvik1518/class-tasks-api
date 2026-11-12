"""What the service needs from storage, written as a promise (a Protocol). Any class with these methods will do:
the SQLite one in production, the in-memory one in tests."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.task import Task


class TaskRepository(Protocol):
    def add(self, title: str, key: str, created_at: datetime) -> Task:
        """Store a new task. Must raise DuplicateTitle if `key` is already taken (the storage's own unique rule)."""

    def get(self, task_id: int) -> Task | None: ...

    def find_by_key(self, key: str) -> Task | None: ...

    def list(self, done: bool | None = None) -> list[Task]:
        """Oldest first (by id). `done=None` means all."""

    def update(self, task: Task) -> None: ...
