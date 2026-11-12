"""The use cases. This is where the rules are applied. It knows nothing about HTTP or SQL:
no status codes, no cursors, no request objects. It can be tested with no server at all."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from app.domain.errors import DuplicateTitle, TaskNotFound
from app.domain.task import Task
from app.domain.titles import check_title, title_key
from app.services.ports import TaskRepository

log = logging.getLogger("classtasks.service")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskService:
    def __init__(self, repository: TaskRepository, max_title_length: int, clock: Callable[[], datetime] = _utc_now):
        self._repo = repository
        self._max_title_length = max_title_length
        self._clock = clock  # injected so a test can say exactly what time it is

    def create(self, raw_title: object) -> Task:
        title = check_title(raw_title, self._max_title_length)
        key = title_key(title)
        # Rule 1, in the service: a quick, friendly check. It is NOT enough on its own: two requests can both pass it.
        if self._repo.find_by_key(key) is not None:
            raise DuplicateTitle(f'There is already a task called "{title}".')
        try:
            # Rule 2, in the database: the one that really guarantees it.
            task = self._repo.add(title, key, self._clock())
        except DuplicateTitle:
            log.info("duplicate stopped by the database rule")
            raise DuplicateTitle(f'There is already a task called "{title}".') from None
        log.info("task created", extra={"task_id": task.id})
        return task

    def list_tasks(self, done: bool | None = None) -> list[Task]:
        return self._repo.list(done)

    def complete(self, task_id: int) -> Task:
        return self._change(task_id, lambda t: t.completed(self._clock()), "task completed")

    def reopen(self, task_id: int) -> Task:
        return self._change(task_id, lambda t: t.reopened(), "task reopened")

    def _change(self, task_id: int, change: Callable[[Task], Task], event: str) -> Task:
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFound(f"There is no task with id {task_id}.")
        changed = change(task)
        if changed is not task:
            self._repo.update(changed)
            log.info(event, extra={"task_id": task_id})
        return changed
