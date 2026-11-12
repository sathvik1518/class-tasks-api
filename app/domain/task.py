"""The Task itself. Frozen: a task never changes in place, a changed copy is made instead,
so two parts of the program can never fight over one object."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    done: bool
    created_at: datetime
    completed_at: datetime | None = None

    def completed(self, now: datetime) -> "Task":
        """Completing a finished task changes nothing (same object back), so a double click is harmless."""
        if self.done:
            return self
        return replace(self, done=True, completed_at=now)

    def reopened(self) -> "Task":
        if not self.done:
            return self
        return replace(self, done=False, completed_at=None)
