"""A pretend database that lives in a dict. Same promise as the SQLite one, so service tests run in microseconds.
It enforces the unique rule too (behind a lock), because the real database does and the pretend one must behave the same."""
from __future__ import annotations

import threading
from datetime import datetime

from app.domain.errors import DuplicateTitle
from app.domain.task import Task


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[int, Task] = {}
        self._keys: dict[str, int] = {}
        self._next_id = 1

    def add(self, title: str, key: str, created_at: datetime) -> Task:
        with self._lock:
            if key in self._keys:
                raise DuplicateTitle("A task with this title already exists.")
            task = Task(id=self._next_id, title=title, done=False, created_at=created_at)
            self._next_id += 1
            self._tasks[task.id] = task
            self._keys[key] = task.id
            return task

    def get(self, task_id: int) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def find_by_key(self, key: str) -> Task | None:
        with self._lock:
            task_id = self._keys.get(key)
            return self._tasks.get(task_id) if task_id is not None else None

    def list(self, done: bool | None = None) -> list[Task]:
        with self._lock:
            tasks = sorted(self._tasks.values(), key=lambda t: t.id)
        return [t for t in tasks if done is None or t.done == done]

    def update(self, task: Task) -> None:
        with self._lock:
            if task.id in self._tasks:  # like SQL's UPDATE ... WHERE id = ?: an unknown id changes nothing (found by the contract test)
                self._tasks[task.id] = task
