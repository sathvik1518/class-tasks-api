"""All the SQL in the project lives in this one file. Every value goes in through a `?` placeholder, never glued into the text."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.domain.errors import DuplicateTitle
from app.domain.task import Task

log = logging.getLogger("classtasks.repository")

# The CHECK below ties `done` and `completed_at` together (and so also rules out any done value except 0 and 1).
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    title_key    TEXT    NOT NULL UNIQUE,
    done         INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    completed_at TEXT,
    CHECK ((done = 0 AND completed_at IS NULL) OR (done = 1 AND completed_at IS NOT NULL))
);
"""


def _to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        done=bool(row["done"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
    )


class SqliteTaskRepository:
    """One short connection per call: simple, and safe when many requests run at once."""

    def __init__(self, path: str | Path):
        self._path = str(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def add(self, title: str, key: str, created_at: datetime) -> Task:
        try:
            with closing(self._connect()) as conn, conn:
                cur = conn.execute(
                    "INSERT INTO tasks (title, title_key, created_at) VALUES (?, ?, ?)",
                    (title, key, created_at.isoformat()),
                )
                task_id = cur.lastrowid
        except sqlite3.IntegrityError as error:
            if str(error).startswith("UNIQUE constraint failed"):
                raise DuplicateTitle("A task with this title already exists.") from None
            raise
        log.debug("row inserted", extra={"task_id": task_id})
        return Task(id=task_id, title=title, done=False, created_at=created_at)

    def get(self, task_id: int) -> Task | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _to_task(row) if row else None

    def find_by_key(self, key: str) -> Task | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE title_key = ?", (key,)).fetchone()
        return _to_task(row) if row else None

    def list(self, done: bool | None = None) -> list[Task]:
        sql, args = "SELECT * FROM tasks", ()
        if done is not None:
            sql, args = sql + " WHERE done = ?", (1 if done else 0,)
        with closing(self._connect()) as conn:
            rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return [_to_task(r) for r in rows]

    def update(self, task: Task) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE tasks SET done = ?, completed_at = ? WHERE id = ?",
                (1 if task.done else 0, task.completed_at.isoformat() if task.completed_at else None, task.id),
            )
        log.debug("row updated", extra={"task_id": task.id})
