# Class Tasks API: Three Layers, Errors Mapped in One Place, Settings That Stop a Bad Start, and One Request ID on Every Log Line

**Day 46 Mini Capstone, Class Tasks API (Architecture)**  
**Project folder:** `class-tasks-api`

---

## 1. Goal

Build a small API for a teacher's class tasks. The task (Day 46, Mini Capstone, *task only*) asked for:

1. **Four endpoints:** create a task, list tasks, complete a task, reopen a task. A task has a title and is done or not done. **Titles are unique.**
2. **Three layers**, with **errors mapped to status codes in one place**.
3. **Settings from the environment**, with a **`.env.example`**.
4. **JSON logs with a request id on every line.**
5. Hints: **start from the "before" code**, refactor in small steps and **run the tests after each one**, and **put the unique rule in the database as well as in the service**.
6. Check yourself: a layer test passes **and fails when you break it**; the service test runs **without a server**; two fast requests with the same title **never make two rows**; a bad `.env` value **stops the app at start-up**; one request id appears on **every log line of that request**; you can **say what you did not test**.

Think of a school office. **The API layer** is the front desk: it takes the request and hands back an answer, and decides nothing. **The service** is the teacher: it knows the rules ("no empty titles, no two tasks with the same name"). **The repository** is the filing cabinet: it only stores and fetches. If the front desk starts making rules, or the filing cabinet starts talking to parents, nobody can change anything without breaking something else. The **request id** is a numbered ticket stapled to every note written about one visit, so when something goes wrong you can pull out exactly that visit.

**What is real and what is not.** Everything here ran for real: FastAPI, a real SQLite file, a real uvicorn server for the concurrency and start-up tests, and real separate Python processes for the start-up checks. The "before" code in this project is **my own version** at the shape the exercises describe (one function doing every job); I could not see the course's Aspect 3 code, so if yours differs, the idea is the same. What was **not** tested is listed in *Known limit*.

---

## 2. Tools

| Tool | Role |
|---|---|
| Python 3.10+ (built and tested on 3.13) | The language |
| FastAPI 0.162.0 | The web layer: routes, request checking, the generated `/docs` page |
| uvicorn 0.54.0 | The server that runs the app; also used inside the tests to get a real server |
| SQLite (built into Python) | The database: a single file, no install |
| pytest 9.1.1 | Runs all the tests |
| httpx 0.28.1 | Test client (FastAPI's `TestClient`) and the real HTTP calls in the concurrency tests |
| `ast` (built in) | Reads the source files to check which layer imports what (the layer test) |

---

## 3. Project structure

```
class-tasks-api/
├── README.md
├── DOCUMENTATION.md
├── .env.example                    (every setting, with its default)
├── .gitignore, pytest.ini
├── requirements.txt, requirements-dev.txt
├── break46.py                      (breaks 64 rules once each; the tests must notice)
├── before/
│   └── before_app.py               (THE "BEFORE": every job in one function; the starting point)
├── app/
│   ├── __main__.py                 (python -m app: start the server, or stop with a clear message)
│   ├── main.py                     (wires the layers together; the only file that knows them all)
│   ├── settings.py                 (environment + .env file, checked at start-up)
│   ├── logging_setup.py            (JSON lines, request id stamped on each)
│   ├── request_context.py          (the request id of the request being served)
│   ├── domain/                     (the rules; plain Python, no HTTP, no SQL)
│   │   ├── task.py, titles.py, errors.py
│   ├── services/                   (the use cases)
│   │   ├── tasks.py, ports.py      (ports.py = the promise a repository must keep)
│   ├── repositories/               (storage; all the SQL is in sqlite.py)
│   │   ├── sqlite.py, memory.py
│   └── api/                        (HTTP only)
│       ├── routes.py, schemas.py, deps.py
│       ├── errors.py               (THE one place that maps an error to a status code)
│       └── middleware.py           (request id + one access line per request)
├── scripts/race_demo.py            (shows the "before" making duplicates under load)
└── tests/
    ├── conftest.py
    ├── test_domain.py, test_service.py, test_repositories.py
    ├── test_api.py, test_errors.py, test_logging.py
    ├── test_settings.py, test_concurrency.py
    ├── test_layers.py, test_before_vs_after.py
```

---

## 4. Setup commands

```bash
# Windows PowerShell (Mac/Linux: source .venv/bin/activate)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

**Commands**

```bash
python -m pytest -q                                   # all 286 tests (about 6 seconds)
python -m app                                         # start the server on http://127.0.0.1:8000  (docs at /docs)
python -m uvicorn app.main:create_app --factory --no-access-log --reload    # same, with auto-reload while you edit
python break46.py                                     # break 64 rules on purpose; every one must be caught
python scripts/race_demo.py                           # watch the "before" make duplicate rows, the new app refuse them
```

---

## 5. The idea: one job per file, one place per decision

**Where each job lives (the answer to "write down every job the before function does").** The "before" `create_task` does eight jobs by itself. After the refactor each job has one home:

| Job | Before | After |
|---|---|---|
| Read a setting | `os.environ[...]` inside the function, on every request | `app/settings.py`, once, at start-up |
| Open the database | inside the function, never closed | `app/repositories/sqlite.py`, closed after every call |
| Clean the title | inside the function | `app/domain/titles.py` |
| Business rules (blank, too long, same title) | inside the function | `app/domain/titles.py` + `app/services/tasks.py` |
| SQL | inside the function | `app/repositories/sqlite.py` only |
| Choose the status code | `raise HTTPException(409, ...)` in the function | `app/api/errors.py` only |
| Shape the answer | a hand-made dict | `app/api/schemas.py` |
| Logging | `print("created", id)` | `app/logging_setup.py` + the request id middleware |

**The three layers and what each may touch.**

| Layer | May use | Must NOT use |
|---|---|---|
| `domain` | plain Python | FastAPI, SQL, the other layers |
| `services` | `domain` | FastAPI, Starlette, Pydantic, SQLite |
| `repositories` | `domain`, SQLite | FastAPI, the service |
| `api` | `services`, `domain`, FastAPI | SQLite, the repositories |
| `main.py` | everything | (it is the only file allowed to know every layer) |

A **layer test** (`tests/test_layers.py`) reads the real source files and fails if a layer imports something it should not. It is itself tested with 20 bad and 5 good sample sources, so the checker cannot quietly stop checking.

**Two unique rules, and why both.** The service checks first ("is this title taken?") so a normal duplicate gets a quick, friendly 409. But two requests can both ask at the same instant, both hear "no", and both insert. The **database `UNIQUE` rule** is the one that really guarantees it: the second insert fails, the repository turns the database's complaint into the app's own `DuplicateTitle`, and the user still gets the same 409. To prove it, the tests make two threads wait at a barrier **after** the friendly check and **before** the insert, so the race happens every time, not once in a while. `scripts/race_demo.py` shows the same thing under load on the "before" code (in the runs for this document: one round made **16 rows** for one title).

**What "the same title" means.** Case does not matter (`Quiz` = `QUIZ` = `quiz`), extra spaces do not matter, accents typed two ways are the same (`é` as one character or as `e` plus an accent), and `Straße` equals `STRASSE`. The database stores a `title_key` column with that normalised form and puts the `UNIQUE` rule on it. A title with only invisible characters (like the zero-width space) counts as empty.

**Errors in one place.** Rule errors (`InvalidTitle`, `DuplicateTitle`, `TaskNotFound`) are plain Python classes with no status code. `app/api/errors.py` holds one table: `InvalidTitle → 422`, `DuplicateTitle → 409`, `TaskNotFound → 404`. A test fails if a new error class has no line in that table, and another test fails if `routes.py`, `deps.py`, `schemas.py` or the service contains `HTTPException` or a status number. Every error answer has the same shape: `{"error": {"code", "message", "request_id", ...}}`, including FastAPI's own validation errors, unknown addresses (404) and wrong methods (405).

**Settings that stop a bad start.** `APP_DATABASE_URL`, `APP_MAX_TITLE_LENGTH` (1 to 500), `APP_LOG_LEVEL`, `APP_PORT`. Real environment variables win over the `.env` file. Every problem is collected and reported together, naming the variable, the bad value and what is allowed. A typo in the `.env` file (`APP_MAX_TITLE_LEN=5`) is an error with "Did you mean APP_MAX_TITLE_LENGTH?" instead of being ignored. `python -m app` prints the message and exits with **code 2 before anything listens**:

```
Cannot start the Class Tasks API.
The settings are not valid:
  - APP_MAX_TITLE_LENGTH='abc' is not a whole number. Use digits only, for example 100.
  - APP_PORT=0 is out of range. Use a number from 1 to 65535.
```

**The request id.** A small middleware makes an id for every request (or keeps the caller's `X-Request-ID` if it is 1 to 64 safe characters, because the id goes into logs), stores it in a `ContextVar` (a variable that is separate per request and follows the work into the thread pool), puts it on the response header and writes one access line. A logging filter stamps that id on every log line, from any layer. One line looks like:

```
{"ts": "2026-11-12T04:40:42.486Z", "level": "INFO", "logger": "classtasks.service", "message": "task created", "request_id": "498f90be13a0432e99ff1504cf3497cb", "task_id": 1}
```

A test fires 40 requests at once at a real server, each with its own id, and checks that every "task created" line carries the id of the request that got that task id, and that no line belongs to any other request. Titles and query strings are never logged.

---

## 6. The code

### `app/domain/errors.py`

```python
"""The ways a task request can be refused. Plain Python: no HTTP, no SQL.
Each error has a stable `code` (for programs) and a `message` (for people). The HTTP status for each lives in ONE place: app/api/errors.py."""


class TaskError(Exception):
    code = "task_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidTitle(TaskError):
    code = "invalid_title"


class DuplicateTitle(TaskError):
    code = "duplicate_title"


class TaskNotFound(TaskError):
    code = "task_not_found"
```

### `app/domain/task.py`

```python
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
```

### `app/domain/titles.py`

```python
"""The rules for a title. One place, so the API, the service and the tests all agree."""
from __future__ import annotations

import unicodedata

from app.domain.errors import InvalidTitle


def normalize_title(raw: str) -> str:
    """Same text in one canonical shape: composed accents (NFC), no outer spaces, runs of white space become one space."""
    return " ".join(unicodedata.normalize("NFC", raw).split())


def title_key(title: str) -> str:
    """What 'the same title' means: ignoring upper/lower case. `Homework` and `HOMEWORK` are one title."""
    return title.casefold()


def _visible(ch: str) -> bool:
    return not ch.isspace() and unicodedata.category(ch) != "Cf"  # Cf = invisible format marks such as the zero-width space


def check_title(raw: object, max_length: int) -> str:
    """Return the cleaned title or raise InvalidTitle. `max_length` comes from the settings."""
    if not isinstance(raw, str):
        raise InvalidTitle("Title must be text.")
    title = normalize_title(raw)
    if any(unicodedata.category(ch) == "Cc" for ch in title):
        raise InvalidTitle("Title can't contain control characters.")
    if not any(_visible(ch) for ch in title):
        raise InvalidTitle("Title can't be empty.")
    if len(title) > max_length:
        raise InvalidTitle(f"Title can be at most {max_length} characters (this one is {len(title)}).")
    return title
```

### `app/services/ports.py`

```python
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
```

### `app/services/tasks.py`

```python
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
```

### `app/repositories/memory.py`

```python
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
```

### `app/repositories/sqlite.py`

```python
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
```

### `app/api/schemas.py`

```python
"""The shapes that cross the wire."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    # `title: str` only checks "is it text". What a GOOD title is (length, blank, duplicates) is a rule, so it lives in the domain.
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str


class TaskOut(BaseModel):
    id: int
    title: str
    done: bool
    created_at: datetime
    completed_at: datetime | None
```

### `app/api/deps.py`

```python
from fastapi import Request

from app.services.tasks import TaskService


def get_service(request: Request) -> TaskService:
    return request.app.state.service
```

### `app/api/routes.py`

```python
"""HTTP only: read the request, call the service, shape the answer. No rules, no SQL, no status-code choices for errors."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.api.deps import get_service
from app.api.schemas import TaskCreate, TaskOut
from app.services.tasks import TaskService

MAX_ID = 2**63 - 1  # the biggest number SQLite can hold; anything bigger would crash the database call

TaskId = Path(ge=1, le=MAX_ID)


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.post("/tasks", status_code=201, response_model=TaskOut)
    def create_task(body: TaskCreate, service: TaskService = Depends(get_service)):
        return service.create(body.title)

    @router.get("/tasks", response_model=list[TaskOut])
    def list_tasks(done: bool | None = None, service: TaskService = Depends(get_service)):
        return service.list_tasks(done)

    @router.post("/tasks/{task_id}/complete", response_model=TaskOut)
    def complete_task(task_id: int = TaskId, service: TaskService = Depends(get_service)):
        return service.complete(task_id)

    @router.post("/tasks/{task_id}/reopen", response_model=TaskOut)
    def reopen_task(task_id: int = TaskId, service: TaskService = Depends(get_service)):
        return service.reopen(task_id)

    return router
```

### `app/api/errors.py` (the one place that maps errors to status codes)

```python
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
```

### `app/api/middleware.py`

```python
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
```

### `app/request_context.py`

```python
"""The request id of the request being served right now. A ContextVar is a variable that is separate for every request
(and follows the work into the thread pool), so two requests at the same time never see each other's id."""
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
```

### `app/logging_setup.py`

```python
"""JSON logs, one object per line, every line carrying the request id of the request that caused it."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import TextIO

from app.request_context import request_id_var

LOGGER_NAME = "classtasks"  # every log line of this app comes from a logger under this name

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    """Stamps the current request id on each record, unless the caller already named one (the 500 handler does)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                data[key] = value  # whatever was passed with extra={...}
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)  # one string: the line stays one line
        return json.dumps(data, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Safe to call again: the old handler is replaced, never stacked (stacking prints every line twice)."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
```

### `app/settings.py`

```python
"""Settings come from the environment (and an optional .env file). Wrong values stop the app at start-up with a clear message,
not on the first request an hour later."""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_DATABASE_URL = "sqlite:///./class_tasks.db"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
KNOWN_KEYS = ("APP_DATABASE_URL", "APP_MAX_TITLE_LENGTH", "APP_LOG_LEVEL", "APP_PORT")


class StartupError(Exception):
    """The app cannot start. The message says why, in plain words."""


class SettingsError(StartupError):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    max_title_length: int = 100
    log_level: str = "INFO"
    port: int = 8000

    @property
    def database_path(self) -> str:
        return self.database_url[len("sqlite:///"):]

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None, env_file: str | Path | None = ".env") -> "Settings":
        """Real environment variables win over the .env file. Every problem is collected, then reported together."""
        environ = os.environ if environ is None else environ
        file_values = read_env_file(env_file) if env_file else {}
        values = {**file_values, **{k: v for k, v in environ.items() if k in KNOWN_KEYS}}
        problems: list[str] = []
        defaults = cls()

        def text(key: str, default: str) -> str | None:
            if key not in values:
                return default
            value = values[key].strip()
            if not value:
                problems.append(f"{key} is set but empty. Remove the line to use the default ({default}), or give it a value.")
                return None
            return value

        def whole_number(key: str, default: int, low: int, high: int) -> int | None:
            raw = text(key, str(default))
            if raw is None:
                return None
            if not re.fullmatch(r"[0-9]+", raw):
                problems.append(f"{key}={raw!r} is not a whole number. Use digits only, for example {default}.")
                return None
            number = int(raw)
            if not low <= number <= high:
                problems.append(f"{key}={number} is out of range. Use a number from {low} to {high}.")
                return None
            return number

        database_url = text("APP_DATABASE_URL", defaults.database_url)
        if database_url is not None:
            if not database_url.startswith("sqlite:///"):
                problems.append(f"APP_DATABASE_URL={database_url!r} is not supported. Use sqlite:///path/to/file.db (this app only knows SQLite).")
                database_url = None
            elif database_url[len("sqlite:///"):] in ("", ":memory:"):
                problems.append("APP_DATABASE_URL needs a real file path after sqlite:/// (an in-memory database would be empty on every connection).")
                database_url = None
        max_title_length = whole_number("APP_MAX_TITLE_LENGTH", defaults.max_title_length, 1, 500)
        port = whole_number("APP_PORT", defaults.port, 1, 65535)
        log_level = text("APP_LOG_LEVEL", defaults.log_level)
        if log_level is not None:
            if log_level.upper() not in LOG_LEVELS:
                problems.append(f"APP_LOG_LEVEL={log_level!r} is not a level. Use one of: {', '.join(LOG_LEVELS)}.")
                log_level = None
            else:
                log_level = log_level.upper()
        for key in file_values:  # a typo in .env would otherwise be ignored silently
            if key not in KNOWN_KEYS:
                hint = difflib.get_close_matches(key, KNOWN_KEYS, n=1)
                problems.append(f"{key} in the .env file is not a setting this app knows." + (f" Did you mean {hint[0]}?" if hint else ""))
        if problems:
            raise SettingsError("The settings are not valid:\n" + "\n".join(f"  - {p}" for p in problems))
        return cls(database_url=database_url, max_title_length=max_title_length, log_level=log_level, port=port)


_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def parse_env_text(text: str) -> dict[str, str]:
    """KEY=value lines. `#` starts a comment. Quotes around a value are removed. Bad lines are reported with their number."""
    values: dict[str, str] = {}
    first_seen: dict[str, int] = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE.match(stripped)
        if not match:
            problems.append(f"line {number}: expected KEY=value, got {stripped!r}")
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw[:1] in ("'", '"'):
            end = raw.find(raw[0], 1)
            value = raw[1:end] if end != -1 else raw[1:]
        else:
            value = re.split(r"\s#", raw, maxsplit=1)[0].strip()
        if key in first_seen:
            problems.append(f"line {number}: {key} is already set on line {first_seen[key]}")
            continue
        first_seen[key] = number
        values[key] = value
    if problems:
        raise SettingsError("The .env file is not valid:\n" + "\n".join(f"  - {p}" for p in problems))
    return values


def read_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None or not Path(path).is_file():
        return {}  # no .env file is fine: the environment and the defaults still work
    return parse_env_text(Path(path).read_text(encoding="utf-8"))
```

### `app/main.py`

```python
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
```

### `app/__main__.py`

```python
"""`python -m app` starts the server. A bad setting prints one clear message and exits with code 2, before anything listens."""
import sys

import uvicorn

from app.main import create_app
from app.settings import Settings, StartupError


def main() -> int:
    try:
        settings = Settings.load()
        app = create_app(settings)
    except StartupError as error:
        print(f"Cannot start the Class Tasks API.\n{error}", file=sys.stderr)
        return 2
    uvicorn.run(app, host="127.0.0.1", port=settings.port, access_log=False)  # our own access line carries the request id
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `before/before_app.py` (the starting point, not for production)

```python
"""THE "BEFORE": every job in one file, one function per endpoint. It works. It is also where we start.
Jobs one create_task does by itself: read a setting, open the database, create the table, validate, run SQL,
choose the status code, shape the answer, print a log line. Not for production: kept only as the starting point."""
import os
import sqlite3

from fastapi import FastAPI, HTTPException

app = FastAPI()


def _conn():
    path = os.environ["APP_DATABASE_URL"].replace("sqlite:///", "")  # job: read a setting (on every request)
    conn = sqlite3.connect(path)  # job: open the database (never closed)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)")
    return conn


def _out(row):
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


@app.post("/tasks", status_code=201)
def create_task(body: dict):
    conn = _conn()
    title = str(body.get("title", "")).strip()  # job: clean the input
    if not title:  # job: a business rule
        raise HTTPException(422, "title required")  # job: pick the status code
    if len(title) > 100:  # job: another rule (the number 100 is hard-coded)
        raise HTTPException(422, "title too long")
    if conn.execute("SELECT 1 FROM tasks WHERE title = ?", (title,)).fetchone():  # job: SQL, rule "a title must be unique"
        raise HTTPException(409, "a title must be unique")  # two requests at the same time can both get past this line
    cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
    conn.commit()
    print("created", cur.lastrowid)  # job: logging (plain text, no request id)
    return {"id": cur.lastrowid, "title": title, "done": False}


@app.get("/tasks")
def list_tasks():
    conn = _conn()
    return [_out(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id")]


def _set_done(task_id: int, done: int):
    conn = _conn()
    if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
        raise HTTPException(404, "no such task")
    conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (done, task_id))
    conn.commit()
    return _out(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    return _set_done(task_id, 1)


@app.post("/tasks/{task_id}/reopen")
def reopen_task(task_id: int):
    return _set_done(task_id, 0)
```

### `.env.example`

```bash
# Copy this file to .env and change what you need:   Copy-Item .env.example .env
# Real environment variables win over this file. Wrong values stop the app at start-up with a message.

# Where tasks are stored. Only SQLite is supported: sqlite:///relative/or/absolute/path.db
APP_DATABASE_URL=sqlite:///./class_tasks.db

# Longest allowed title, in characters (1 to 500)
APP_MAX_TITLE_LENGTH=100

# DEBUG, INFO, WARNING or ERROR
APP_LOG_LEVEL=INFO

# Port to listen on (1 to 65535). The server listens on 127.0.0.1 only.
APP_PORT=8000
```

### `requirements.txt`

```text
fastapi==0.162.0
uvicorn==0.54.0
```

### `requirements-dev.txt`

```text
-r requirements.txt
pytest==9.1.1
httpx==0.28.1
```

### `pytest.ini`

```ini
[pytest]
pythonpath = .
testpaths = tests
```

### `.gitignore`

```text
.venv/
__pycache__/
.pytest_cache/
.env
*.db
*.db-journal
```

### `scripts/race_demo.py`

```python
"""Shows the 'before' app making duplicate rows when many requests with the same title arrive together,
then the new app refusing them. Timing-based: how many duplicates you see changes from run to run (that is the point of a race).
Run from the project folder:   python scripts/race_demo.py"""
import os
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

REQUESTS, ROUNDS = 40, 5


def serve(app):
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}"


def blast(base, title):
    barrier = threading.Barrier(REQUESTS, timeout=20)

    def go(_):
        barrier.wait()
        return httpx.post(f"{base}/tasks", json={"title": title}, timeout=60).status_code

    with ThreadPoolExecutor(max_workers=REQUESTS) as pool:
        return list(pool.map(go, range(REQUESTS)))


def main():
    tmp = Path(tempfile.mkdtemp())
    os.environ["APP_DATABASE_URL"] = f"sqlite:///{tmp / 'before.db'}"
    from before.before_app import app as before_app
    for name, app, db in (("before", before_app, tmp / "before.db"), ("after", create_app(Settings(database_url=f"sqlite:///{tmp / 'after.db'}", log_level="ERROR")), tmp / "after.db")):
        server, base = serve(app)
        rows = []
        for round_no in range(ROUNDS):
            codes = blast(base, f"Same title {round_no}")
            with sqlite3.connect(db) as conn:
                rows.append(conn.execute("SELECT COUNT(*) FROM tasks WHERE title = ?", (f"Same title {round_no}",)).fetchone()[0])
        server.should_exit = True
        print(f"{name}: rows made per round (should be 1 each): {rows}")


main()
```

### `break46.py`

```python
"""Break each rule once on purpose and check that the tests notice.
Run from the project folder:   python break46.py            (all)     or    python break46.py "unique" "request id"   (only names that contain a word)
Each case edits one file, runs the whole test suite, expects it to FAIL, then puts the file back."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
APP = ROOT / "app"

# (name, file, old text, new text)
CASES = [
  # ---- domain: title rules ----
  ("title: accents not joined (no NFC)", APP/"domain/titles.py", 'unicodedata.normalize("NFC", raw).split()', "raw.split()"),
  ("title: spaces inside not collapsed", APP/"domain/titles.py", 'return " ".join(unicodedata.normalize("NFC", raw).split())', "return unicodedata.normalize('NFC', raw).strip()"),
  ("title key: lower() instead of casefold()", APP/"domain/titles.py", "return title.casefold()", "return title.lower()"),
  ("title key: case matters", APP/"domain/titles.py", "return title.casefold()", "return title"),
  ("title: control characters allowed", APP/"domain/titles.py", 'unicodedata.category(ch) == "Cc" for ch in title', 'unicodedata.category(ch) == "Zz" for ch in title'),
  ("title: invisible marks count as visible", APP/"domain/titles.py", 'unicodedata.category(ch) != "Cf"', 'unicodedata.category(ch) != "Zz"'),
  ("title: limit off by one (>= instead of >)", APP/"domain/titles.py", "if len(title) > max_length:", "if len(title) >= max_length:"),
  ("title: length limit not checked", APP/"domain/titles.py", "if len(title) > max_length:", "if False:"),
  ("title: non-text accepted", APP/"domain/titles.py", "if not isinstance(raw, str):", "if False:"),
  ("title: blank titles accepted", APP/"domain/titles.py", "if not any(_visible(ch) for ch in title):", "if False:"),
  # ---- domain: task ----
  ("complete: a done task gets a new time", APP/"domain/task.py", "        if self.done:\n            return self\n        return replace(self, done=True", "        return replace(self, done=True"),
  ("reopen: the finish time is kept", APP/"domain/task.py", "replace(self, done=False, completed_at=None)", "replace(self, done=False)"),
  ("complete: no finish time set", APP/"domain/task.py", "replace(self, done=True, completed_at=now)", "replace(self, done=True)"),
  ("task is not frozen", APP/"domain/task.py", "@dataclass(frozen=True)", "@dataclass"),
  # ---- service ----
  ("service: friendly duplicate check removed", APP/"services/tasks.py", "if self._repo.find_by_key(key) is not None:", "if False:"),
  ("service: database duplicate not given the friendly message", APP/"services/tasks.py", "        except DuplicateTitle:\n            log.info", "        except ZeroDivisionError:\n            log.info"),
  ("service: clock not injected", APP/"services/tasks.py", "self._clock = clock  #", "self._clock = _utc_now  #"),
  ("service: writes even when nothing changed", APP/"services/tasks.py", "if changed is not task:", "if True:"),
  ("service: missing task not noticed", APP/"services/tasks.py", "        if task is None:\n            raise TaskNotFound", "        if False:\n            raise TaskNotFound"),
  ("service: title limit hard-coded", APP/"services/tasks.py", "check_title(raw_title, self._max_title_length)", "check_title(raw_title, 100)"),
  # ---- repositories ----
  ("database: UNIQUE rule removed", APP/"repositories/sqlite.py", "title_key    TEXT    NOT NULL UNIQUE,", "title_key    TEXT    NOT NULL,"),
  ("database: done/time consistency rule removed", APP/"repositories/sqlite.py", "    completed_at TEXT,\n    CHECK ((done = 0 AND completed_at IS NULL) OR (done = 1 AND completed_at IS NOT NULL))\n", "    completed_at TEXT\n"),
  ("SQL: value glued into the text", APP/"repositories/sqlite.py", 'conn.execute("SELECT * FROM tasks WHERE title_key = ?", (key,)).fetchone()', "conn.execute(f\"SELECT * FROM tasks WHERE title_key = '{key}'\").fetchone()"),
  ("SQL: done filter inverted", APP/"repositories/sqlite.py", "(1 if done else 0,)", "(0 if done else 1,)"),
  ("database: any integrity error called a duplicate", APP/"repositories/sqlite.py", 'if str(error).startswith("UNIQUE constraint failed"):', "if True:"),
  ("database: schema never created", APP/"main.py", "            sqlite_repo.init_schema()", "            pass"),
  ("pretend database: no unique rule", APP/"repositories/memory.py", "            if key in self._keys:", "            if False:"),
  ("pretend database: update of a missing id creates it", APP/"repositories/memory.py", "            if task.id in self._tasks:", "            if True:"),
  # ---- api ----
  ("api: extra fields accepted", APP/"api/schemas.py", 'ConfigDict(extra="forbid", strict=True)', "ConfigDict(strict=True)"),
  ("api: id range not checked (huge id crashes the database)", APP/"api/routes.py", "TaskId = Path(ge=1, le=MAX_ID)", "TaskId = Path()"),
  ("api: duplicate answers 400 instead of 409", APP/"api/errors.py", "DuplicateTitle: 409,", "DuplicateTitle: 400,"),
  ("api: not-found error has no status", APP/"api/errors.py", "    TaskNotFound: 404,\n", ""),
  ("api: filter ignored", APP/"api/routes.py", "return service.list_tasks(done)", "return service.list_tasks()"),
  ("api: create answers 200 instead of 201", APP/"api/routes.py", '@router.post("/tasks", status_code=201', '@router.post("/tasks", status_code=200'),
  ("api: validation answer echoes the input", APP/"api/errors.py", '"problem": item.get("msg", "Invalid value.")}', '"problem": item.get("msg", "Invalid value."), "input": item.get("input")}'),
  ("api: 500 leaks the real error text", APP/"api/errors.py", '"Something went wrong on our side. Quote the request id if you ask for help."', 'f"Something went wrong: {error}"'),
  ("api: 500 has no request id header", APP/"api/errors.py", 'headers={"X-Request-ID": rid} if rid else None', "headers=None"),
  ("api: unknown address code changed", APP/"api/errors.py", '404: "not_found"', '404: "missing"'),
  ("api: 405 loses its Allow header", APP/"api/errors.py", "headers=error.headers", "headers=None"),
  # ---- request id and logs ----
  ("request id: any incoming id accepted", APP/"api/middleware.py", "if incoming and _SAFE_ID.fullmatch(incoming):", "if incoming:"),
  ("request id: length limit loosened", APP/"api/middleware.py", "{1,64}", "{1,200}"),
  ("request id: not put on the response", APP/"api/middleware.py", "MutableHeaders(scope=message)[HEADER] = rid", "pass"),
  ("logs: query string logged", APP/"api/middleware.py", '"path": scope["path"],', '"path": scope["path"] + "?" + scope["query_string"].decode(),'),
  ("logs: request id filter removed", APP/"logging_setup.py", "    handler.addFilter(RequestIdFilter())\n", ""),
  ("logs: extra fields dropped", APP/"logging_setup.py", "                data[key] = value  # whatever", "                pass  # whatever"),
  ("logs: handlers stack up (lines printed twice)", APP/"logging_setup.py", "        logger.removeHandler(handler)", "        pass"),
  ("logs: line not JSON", APP/"logging_setup.py", "return json.dumps(data, default=str, ensure_ascii=False)", "return str(data)"),
  ("logs: no access line", APP/"api/middleware.py", '            log.info(\n                "request finished",', '            (lambda *a, **k: None)(\n                "request finished",'),
  # ---- settings ----
  ("settings: Unicode digits accepted", APP/"settings.py", 're.fullmatch(r"[0-9]+", raw)', 're.fullmatch(r"\\d+", raw)'),
  ("settings: title limit range widened", APP/"settings.py", '"APP_MAX_TITLE_LENGTH", defaults.max_title_length, 1, 500', '"APP_MAX_TITLE_LENGTH", defaults.max_title_length, 1, 5000'),
  ("settings: .env beats the real environment", APP/"settings.py", "values = {**file_values, **{k: v for k, v in environ.items() if k in KNOWN_KEYS}}", "values = {**{k: v for k, v in environ.items() if k in KNOWN_KEYS}, **file_values}"),
  ("settings: typo in .env ignored", APP/"settings.py", "            if key not in KNOWN_KEYS:", "            if False:"),
  ("settings: empty value silently accepted", APP/"settings.py", "            if not value:", "            if False:"),
  ("settings: repeated key in .env accepted", APP/"settings.py", "        if key in first_seen:", "        if False:"),
  ("settings: in-memory database accepted", APP/"settings.py", 'in ("", ":memory:")', 'in ("",)'),
  ("start-up: bad settings exit with code 0", APP/"__main__.py", "        return 2", "        return 0"),
  ("start-up: uvicorn's own access log left on", APP/"__main__.py", "access_log=False", "access_log=True"),
  ("start-up: database error not turned into a clear message", APP/"main.py", '            raise StartupError(f"Cannot open the database at {settings.database_path!r}: {error}") from None', "            raise"),
  # ---- layers ----
  ("layer: service imports fastapi", APP/"services/tasks.py", "import logging\nfrom datetime", "import logging\nimport fastapi\nfrom datetime"),
  ("layer: service imports sqlite3", APP/"services/tasks.py", "import logging\nfrom datetime", "import logging\nimport sqlite3\nfrom datetime"),
  ("layer: api imports sqlite3", APP/"api/routes.py", "from fastapi import APIRouter, Depends, Path", "import sqlite3\nfrom fastapi import APIRouter, Depends, Path"),
  ("layer: api imports the sqlite repository", APP/"api/deps.py", "from fastapi import Request", "from fastapi import Request\nfrom app.repositories.sqlite import SqliteTaskRepository"),
  ("layer: domain imports fastapi", APP/"domain/titles.py", "import unicodedata\n", "import unicodedata\nimport fastapi\n"),
  ("layer: repository imports the service", APP/"repositories/memory.py", "import threading\n", "import threading\nfrom app.services.tasks import TaskService\n"),
]


def suite_fails() -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode != 0


def main(words):
    chosen = [c for c in CASES if not words or any(w.lower() in c[0].lower() for w in words)]
    assert not suite_fails(), "the tests must pass before anything is broken"
    survivors = []
    for name, path, old, new in chosen:
        original = path.read_text()
        if original.count(old) != 1:
            print(f"BAD CASE (text found {original.count(old)} times): {name}")
            survivors.append(name)
            continue
        try:
            path.write_text(original.replace(old, new))
            caught = suite_fails()
        finally:
            path.write_text(original)
        print(("caught   " if caught else "MISSED   ") + name)
        if not caught:
            survivors.append(name)
    assert not suite_fails(), "files were not restored"
    print(f"\n{len(chosen) - len(survivors)} of {len(chosen)} mistakes caught")
    if survivors:
        print("NOT caught:", *survivors, sep="\n  - ")
        sys.exit(1)


main(sys.argv[1:])
```

### Design decisions

| Decision | Reason |
|---|---|
| Three layers: domain, services, repositories, plus an `api` layer for HTTP | Each file has one reason to change. A new rule touches the service; a new database touches one repository file; a new status code touches one table |
| Domain errors carry a `code` and a message, never a status number | The rules should not know they are served over HTTP; a command-line tool could reuse them |
| One table `STATUS_FOR_ERROR` in `app/api/errors.py` | The brief says errors are mapped in one place. A test fails if a new error is missing from it, and another if routes or the service pick a status themselves |
| The repository promise is a `Protocol` in `services/ports.py` | The service depends on a promise, not on SQLite. The test double and the real repository both keep it, and a contract test proves they behave the same |
| A pretend in-memory repository for service tests | Service tests run with no server and no file; a test proves that importing the service pulls in neither FastAPI nor SQLite |
| Contract test runs the same cases on both repositories | It found a real difference on the first run: updating a task that does not exist created it in the pretend repository, but did nothing in SQLite. The pretend one was fixed to match |
| `Task` is a frozen dataclass; `completed()` and `reopened()` return a changed copy | Nothing can change a task behind the service's back; completing a done task returns the same object, so no second write happens |
| Completing a done task and reopening an open task are not errors | A double click or a retry must be harmless; the first completion time is kept |
| Title rules in one function (`check_title`), limit from a setting | The API, the service and the tests use the same rules; `APP_MAX_TITLE_LENGTH` changes the limit without touching code |
| The Pydantic schema only checks 'is it text', with `extra=forbid` | What a good title is belongs in the domain. Unknown fields are refused so a typo like `titel` is a clear 422, not a silent ignore |
| Same title = same `casefold()` of the cleaned text, stored in a `title_key` column with `UNIQUE` | `lower()` misses `Straße` vs `STRASSE`; the database rule needs one exact value to compare |
| Friendly check in the service AND `UNIQUE` in the database | The service check gives a nice quick answer; only the database can stop two simultaneous requests |
| The repository turns only the UNIQUE failure into `DuplicateTitle` | Any other integrity error must stay loud; a test proves a NOT NULL failure is not called a duplicate |
| A `CHECK` ties `done` and `completed_at` together | The database itself refuses 'done with no time' and 'open with a time', even if some future code forgets |
| One short SQLite connection per call, values always through `?` | Safe when many requests overlap; a title like `x'); DROP TABLE tasks;--` is stored as plain text |
| Task ids are limited to 1 to 2^63-1 in the route | SQLite cannot hold a bigger number; without the limit `/tasks/99999999999999999999/complete` crashes with a 500 |
| Every error answer has the same JSON shape, validation errors never echo the input | One shape for client code to read; echoing input back can leak secrets sent by mistake |
| Settings are read once at start-up and collected into one error report | A bad value fails in the first second, naming everything wrong, not on the first request later |
| Unknown keys are errors in the `.env` file but ignored in the environment | A typo in `.env` is a real mistake; the environment of a computer holds many unrelated variables |
| Real environment variables beat the `.env` file | The usual rule: a server can override a laptop file without editing it |
| In-memory SQLite (`sqlite:///:memory:`) is refused | Each short connection would see its own empty database |
| `python -m app` exits with code 2 and a plain message; `create_app` raises `StartupError` | A person gets a sentence, not a traceback; a script can test the exit code |
| Request id from a `ContextVar`, set by a pure ASGI middleware | Works for the threads FastAPI uses for normal functions; two simultaneous requests never share an id (tested with 40 at once) |
| An incoming `X-Request-ID` is kept only if 1 to 64 of `A-Za-z0-9._-` | The id goes into log lines; spaces, new lines or long text could forge or flood the log |
| The 500 handler puts the request id on the response itself | In Starlette that handler runs outside the middleware, so without this a crash would be the one answer with no id |
| Logs are one JSON object per line, query strings and titles are not logged | Easy for programs to read; the query string and a title can hold personal data |
| `configure_logging` replaces its handler instead of adding one | Adding one each time prints every line twice (a test and a break-it case watch this) |
| uvicorn's own access log is turned off | Our access line is the one that carries the request id |
| `before/before_app.py` is kept, with a test that runs the same black-box checks on it and on the new app | Proves the refactor did not change what a user sees; a second test lists what the 'before' got wrong |

---

## 7. Tests (286 tests)

Each group answers one of the *Check yourself* items:

| Check yourself | Where |
|---|---|
| (1) A layer test passes, and fails when you break it | `test_layers.py` (47) plus 6 break-it cases in `break46.py` |
| (2) The service test runs without a server | `test_service.py` (17): pretend repository, fake clock, and a clean-process test that FastAPI, Starlette, Pydantic, SQLite and uvicorn are **not imported**. All 17 run in 0.07 s; the 35 API tests take 0.62 s |
| (3) Two fast requests with the same title never make two rows | `test_concurrency.py` (5, real server) and the barrier tests in `test_service.py` and `test_repositories.py` |
| (4) A bad `.env` value stops the app at start-up | `test_settings.py` (54): runs the real `python -m app` as a separate process and checks exit code 2, the message, and that nothing listens |
| (5) One request id on every log line of that request | `test_logging.py` (44), `test_errors.py` (7) |
| (6) You can say what you did not test | *Known limit*, below |

Run `python break46.py` to see the other side: it breaks **64 rules**, one at a time (the unique rule removed, a status code changed, the request id filter removed, a service importing FastAPI, a typo in `.env` ignored, SQL glued into text, ...), runs the whole suite each time and expects it to fail. Result: **64 of 64 caught**.

| # | Test | What it proves |
|---|---|---|
| 1 | Domain rules (30) | Spaces, new lines and accents are cleaned; `Straße` = `STRASSE`; blank, zero-width-only and control-character titles refused; non-text refused; the length limit is inclusive and counted after cleaning; Telugu and emoji work; completing and reopening return changed copies; completing twice returns the same object; a Task cannot be changed in place |
| 2 | Service, no server (17) | Importing the service pulls in no FastAPI or SQLite; create cleans the title; ids count up; duplicates refused ignoring case and spaces (also against a done task); an invalid title never reaches the repository; the friendly check stops a duplicate before the insert; the limit comes from the setting; complete keeps the first time; reopening an open task writes nothing; unknown ids; the done filter; **two threads that both pass the friendly check: one task, one `DuplicateTitle`, and the message names the title** |
| 3 | Repository contract, both repositories (30) | Same cases on the pretend and the SQLite repository: add, get, find, unique rule, a refused duplicate does not use up an id, order and filter, update and reopen, timezones, Unicode, update of a missing id. SQLite only: the unique index exists; the database refuses a duplicate with no app involved; refuses done-without-time, open-with-time and done=2; SQL in a title is stored as text; data survives a new object; **8 threads inserting one key leave one row**; the service over real SQLite catches the race; only a UNIQUE failure counts as a duplicate |
| 4 | API (35) | 201 with the full task; list; complete and reopen; idempotent complete; the filter; 409 duplicate; 422 for 5 bad titles; 422 for 7 wrong shapes; non-JSON body; missing body; the answer never echoes input; 404 for unknown ids; 422 (not a crash) for 6 bad ids; the biggest valid id is a clean 404; bad filter value; 404 and 405 (with `Allow`); every error has the same shape; HTML and SQL titles stored as text; `/openapi.json` |
| 5 | Errors in one place (7) | Every domain error has a status; the table holds only client errors; routes, deps, schemas and the service contain no `HTTPException` and no status number; an unmapped error answers 500 and is logged; an unexpected error gives a 500 without leaking details, with the request id in body and header, logged once with the traceback |
| 6 | Logging and request id (44) | Every line is JSON with the basic fields; one id on every line across all three layers; different requests get different ids; a safe incoming id is kept; 17 unsafe or safe-id cases decide keep or replace; the header is on every kind of answer; error lines carry the id; the access line fields; no query string and no titles logged; the log level filters; configuring twice does not duplicate; a message with a new line is still one line; **40 simultaneous requests: ids never mix** |
| 7 | Settings and start-up (54) | Defaults; environment values; trimming; 10 bad numbers; range edges; port, level and database URL rules; an empty value is an error; all problems reported together; unrelated variables ignored; `.env` parsing (comments, quotes, `export`, bad lines with numbers, duplicate keys); the real environment beats `.env`; a typo gets a hint; `.env.example` is valid and documents exactly the known settings; `.env` is git-ignored; **real processes**: a bad value, a bad `.env` and an unopenable database each exit with code 2 and a plain message, and a good start answers `/health` and writes a JSON line with the request id |
| 8 | Concurrency, real server (5) | Two and thirty identical titles at once: one 201, the rest 409, one row; the same title in four spellings at once: one row; thirty different titles at once: thirty distinct ids; ten simultaneous completes of one task are harmless |
| 9 | Layers (47) | One test per source file (22) that it imports only what its layer allows; 20 sample sources the checker must reject (service importing FastAPI, SQLite or the API; domain importing Pydantic; API importing SQLite or the repositories; relative imports; imports inside a function ...); 5 it must allow |
| 10 | Before vs after (17) | The same 8 black-box checks run on the old code and the new code (create, list, trim, duplicate, bad titles, complete, reopen, 404); and a test that lists what the 'before' got wrong: no case rule, no timestamps, no request id, no unique rule in the database |

### `tests/conftest.py` (shared fixtures: fake clock, pretend repository, real test server)

```python
import io
import json
import socket
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.memory import InMemoryTaskRepository
from app.repositories.sqlite import SqliteTaskRepository
from app.services.tasks import TaskService
from app.settings import Settings


class FakeClock:
    """Time that only moves when the test says so."""

    def __init__(self):
        self.now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def memory_service(clock):
    """A service with a pretend database. No server, no file, no HTTP."""
    return TaskService(InMemoryTaskRepository(), max_title_length=100, clock=clock)


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'tasks.db'}", max_title_length=100, log_level="DEBUG", port=8000)


@pytest.fixture
def sqlite_repo(tmp_path):
    repo = SqliteTaskRepository(tmp_path / "repo.db")
    repo.init_schema()
    return repo


@pytest.fixture
def log_stream():
    return io.StringIO()


@pytest.fixture
def app(settings, log_stream, clock):
    return create_app(settings, log_stream=log_stream, clock=clock)


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def log_lines(stream: io.StringIO) -> list[dict]:
    """Every line must be valid JSON on its own; json.loads fails the test if one is not."""
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


class LiveServer:
    def __init__(self, base_url, stream):
        self.base_url = base_url
        self.stream = stream


@pytest.fixture
def live_server(settings, log_stream):
    """A real uvicorn server on a free port, so requests really overlap."""
    app = create_app(settings, log_stream=log_stream)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("test server did not start")
    yield LiveServer(f"http://127.0.0.1:{port}", log_stream)
    server.should_exit = True
    thread.join(timeout=10)
```

### `tests/test_domain.py`

```python
import pytest

from app.domain.errors import DuplicateTitle, InvalidTitle, TaskError, TaskNotFound
from app.domain.task import Task
from app.domain.titles import check_title, normalize_title, title_key
from datetime import datetime, timezone

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_normalize_trims_and_collapses_spaces():
    assert normalize_title("  Math   homework \t") == "Math homework"


def test_normalize_turns_newlines_into_one_space():
    assert normalize_title("Read\n\nchapter\r\n4") == "Read chapter 4"


def test_normalize_joins_split_accents():
    assert normalize_title("Café") == normalize_title("Café") == "Café"


def test_title_key_uses_full_case_folding():
    assert title_key("Straße") == title_key("STRASSE")  # lower() would keep these apart; casefold() does not


def test_title_key_ignores_case():
    assert title_key("Homework") == title_key("HOMEWORK") == title_key("homework")


@pytest.mark.parametrize("raw", ["", "   ", "\n\t", "​", " ​​ ", " "])
def test_blank_or_invisible_titles_are_refused(raw):
    with pytest.raises(InvalidTitle, match="empty"):
        check_title(raw, 100)


@pytest.mark.parametrize("raw", ["bad\x00name", "esc\x1b[31m", "bell\x07"])
def test_control_characters_are_refused(raw):
    with pytest.raises(InvalidTitle, match="control"):
        check_title(raw, 100)


@pytest.mark.parametrize("raw", [None, 5, 1.5, ["a"], {"a": 1}, b"abc"])
def test_non_text_is_refused(raw):
    with pytest.raises(InvalidTitle, match="text"):
        check_title(raw, 100)


def test_length_limit_is_inclusive():
    assert check_title("a" * 100, 100) == "a" * 100
    with pytest.raises(InvalidTitle, match="at most 100"):
        check_title("a" * 101, 100)


def test_length_is_counted_after_cleaning():
    assert check_title("  " + "a" * 100 + "  ", 100) == "a" * 100
    assert check_title("a  b", 3) == "a b"  # two spaces count as one


def test_length_limit_comes_from_the_argument():
    with pytest.raises(InvalidTitle):
        check_title("abcdef", 5)
    assert check_title("abcdef", 6) == "abcdef"


def test_telugu_and_emoji_titles_are_fine():
    assert check_title("గృహపాఠం 📚", 100) == "గృహపాఠం 📚"


def test_zero_width_joiner_inside_a_word_is_kept():
    assert check_title("క‍ష", 100) == "క‍ష"  # invisible marks are allowed next to visible letters


def test_complete_sets_the_time_and_does_not_touch_the_old_object():
    task = Task(1, "a", False, NOW)
    later = datetime(2026, 1, 2, tzinfo=timezone.utc)
    done = task.completed(later)
    assert done.done and done.completed_at == later
    assert not task.done and task.completed_at is None


def test_completing_a_done_task_returns_the_same_object():
    done = Task(1, "a", True, NOW, NOW)
    assert done.completed(datetime(2030, 1, 1, tzinfo=timezone.utc)) is done


def test_reopen_clears_the_time_and_is_a_noop_when_open():
    done = Task(1, "a", True, NOW, NOW)
    open_ = done.reopened()
    assert not open_.done and open_.completed_at is None
    assert open_.reopened() is open_


def test_task_is_frozen():
    with pytest.raises(Exception):
        Task(1, "a", False, NOW).title = "b"  # type: ignore[misc]


def test_every_error_is_a_task_error_with_a_code():
    codes = set()
    for cls in (InvalidTitle, DuplicateTitle, TaskNotFound):
        assert issubclass(cls, TaskError)
        codes.add(cls.code)
    assert len(codes) == 3 and "task_error" not in codes
    assert InvalidTitle("x").message == "x"
```

### `tests/test_service.py`

```python
"""Service tests: NO server, NO database file, NO HTTP. A pretend repository and a fake clock."""
import subprocess
import sys
import threading
from datetime import timedelta
from pathlib import Path

import pytest

from app.domain.errors import DuplicateTitle, InvalidTitle, TaskNotFound
from app.repositories.memory import InMemoryTaskRepository
from app.services.tasks import TaskService

ROOT = Path(__file__).resolve().parent.parent


def test_service_imports_without_fastapi_or_sqlite():
    """Proof that the service can run with no server: in a clean Python, importing it pulls in neither."""
    code = (
        "import sys, app.services.tasks, app.repositories.memory;"
        "bad = [m for m in ('fastapi', 'starlette', 'pydantic', 'sqlite3', 'uvicorn') if m in sys.modules];"
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_create_returns_a_cleaned_open_task(memory_service, clock):
    task = memory_service.create("  Math   homework ")
    assert (task.id, task.title, task.done, task.completed_at) == (1, "Math homework", False, None)
    assert task.created_at == clock.now


def test_ids_count_up(memory_service):
    assert [memory_service.create(t).id for t in ("a", "b", "c")] == [1, 2, 3]


def test_list_is_oldest_first(memory_service):
    for t in ("c", "a", "b"):
        memory_service.create(t)
    assert [t.title for t in memory_service.list_tasks()] == ["c", "a", "b"]


def test_duplicate_title_is_refused_ignoring_case_and_spaces(memory_service):
    memory_service.create("Math homework")
    for again in ("math homework", "MATH   HOMEWORK", "  Math homework  "):
        with pytest.raises(DuplicateTitle):
            memory_service.create(again)
    assert len(memory_service.list_tasks()) == 1


def test_duplicate_message_names_the_title(memory_service):
    memory_service.create("Quiz")
    with pytest.raises(DuplicateTitle, match='"quiz"'):
        memory_service.create("quiz")


def test_a_done_task_still_blocks_its_title(memory_service):
    t = memory_service.create("Quiz")
    memory_service.complete(t.id)
    with pytest.raises(DuplicateTitle):
        memory_service.create("quiz")


def test_invalid_title_never_reaches_the_repository():
    class Spy(InMemoryTaskRepository):
        calls = 0

        def add(self, *a, **k):
            Spy.calls += 1
            return super().add(*a, **k)

    service = TaskService(Spy(), 100)
    for bad in ("", "  ", None, "x" * 101):
        with pytest.raises(InvalidTitle):
            service.create(bad)
    assert Spy.calls == 0


def test_the_friendly_check_stops_a_duplicate_before_the_insert():
    class Spy(InMemoryTaskRepository):
        adds = 0

        def add(self, *a, **k):
            Spy.adds += 1
            return super().add(*a, **k)

    service = TaskService(Spy(), 100)
    service.create("Quiz")
    with pytest.raises(DuplicateTitle):
        service.create("quiz")
    assert Spy.adds == 1


def test_max_title_length_setting_is_used():
    service = TaskService(InMemoryTaskRepository(), max_title_length=5)
    service.create("12345")
    with pytest.raises(InvalidTitle, match="at most 5"):
        service.create("123456")


def test_complete_sets_done_and_the_time(memory_service, clock):
    t = memory_service.create("a")
    clock.advance(hours=2)
    done = memory_service.complete(t.id)
    assert done.done and done.completed_at == clock.now and done.created_at != done.completed_at


def test_completing_twice_keeps_the_first_time(memory_service, clock):
    t = memory_service.create("a")
    first = memory_service.complete(t.id)
    clock.advance(days=1)
    second = memory_service.complete(t.id)
    assert second.completed_at == first.completed_at


def test_reopen_clears_done_and_time(memory_service):
    t = memory_service.create("a")
    memory_service.complete(t.id)
    back = memory_service.reopen(t.id)
    assert not back.done and back.completed_at is None
    assert memory_service.list_tasks()[0] == back


def test_reopen_an_open_task_changes_nothing_and_writes_nothing():
    class Spy(InMemoryTaskRepository):
        updates = 0

        def update(self, task):
            Spy.updates += 1
            super().update(task)

    service = TaskService(Spy(), 100)
    t = service.create("a")
    service.reopen(t.id)
    assert Spy.updates == 0


def test_unknown_task_ids(memory_service):
    for action in (memory_service.complete, memory_service.reopen):
        with pytest.raises(TaskNotFound, match="999"):
            action(999)


def test_list_filters_by_done(memory_service):
    a, b = memory_service.create("a"), memory_service.create("b")
    memory_service.complete(a.id)
    assert [t.title for t in memory_service.list_tasks(done=True)] == ["a"]
    assert [t.title for t in memory_service.list_tasks(done=False)] == ["b"]
    assert len(memory_service.list_tasks()) == 2


def test_the_database_rule_catches_what_the_friendly_check_missed():
    """Two requests both pass the friendly check (the barrier makes sure of it), then both insert.
    Only the unique rule in the storage can stop the second one."""
    barrier = threading.Barrier(2, timeout=5)

    class BlindSpot(InMemoryTaskRepository):
        def find_by_key(self, key):
            found = super().find_by_key(key)
            barrier.wait()  # both threads have now looked and found nothing
            return found

    repo = BlindSpot()
    service = TaskService(repo, 100)
    results = []

    def attempt():
        try:
            results.append(service.create("Same title"))
        except DuplicateTitle as error:
            results.append(error)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(type(r).__name__ for r in results) == ["DuplicateTitle", "Task"]
    assert 'There is already a task called "Same title"' in [str(r) for r in results if isinstance(r, DuplicateTitle)][0]
    assert len(repo.list()) == 1
```

### `tests/test_repositories.py`

```python
"""One set of tests, run against BOTH repositories (contract test). If the pretend one drifts from the real one, a test here fails."""
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.errors import DuplicateTitle
from app.domain.titles import title_key
from app.repositories.memory import InMemoryTaskRepository
from app.repositories.sqlite import SqliteTaskRepository
from app.services.tasks import TaskService

T0 = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        return InMemoryTaskRepository()
    r = SqliteTaskRepository(tmp_path / "c.db")
    r.init_schema()
    return r


def add(repo, title, when=T0):
    return repo.add(title, title_key(title), when)


def test_add_returns_an_open_task_with_an_id(repo):
    t = add(repo, "Quiz")
    assert (t.id, t.title, t.done, t.completed_at, t.created_at) == (1, "Quiz", False, None, T0)


def test_get_gives_back_what_was_added(repo):
    t = add(repo, "Quiz")
    assert repo.get(t.id) == t
    assert repo.get(999) is None


def test_find_by_key(repo):
    t = add(repo, "Quiz")
    assert repo.find_by_key("quiz") == t
    assert repo.find_by_key("nope") is None


def test_the_unique_rule_is_in_the_repository(repo):
    add(repo, "Quiz")
    with pytest.raises(DuplicateTitle):
        add(repo, "QUIZ")
    assert len(repo.list()) == 1


def test_a_refused_duplicate_does_not_use_up_an_id(repo):
    add(repo, "a")
    with pytest.raises(DuplicateTitle):
        add(repo, "A")
    assert add(repo, "b").id == 2


def test_list_is_ordered_by_id_and_filters(repo):
    a, b, c = add(repo, "a"), add(repo, "b"), add(repo, "c")
    repo.update(b.completed(T0 + timedelta(hours=1)))
    assert [t.id for t in repo.list()] == [1, 2, 3]
    assert [t.id for t in repo.list(done=True)] == [2]
    assert [t.id for t in repo.list(done=False)] == [1, 3]


def test_update_saves_done_and_time_and_reopen_clears_them(repo):
    t = add(repo, "a")
    done = t.completed(T0 + timedelta(hours=3))
    repo.update(done)
    assert repo.get(t.id) == done
    repo.update(done.reopened())
    assert repo.get(t.id) == t


def test_datetimes_keep_their_timezone(repo):
    t = add(repo, "a")
    assert repo.get(t.id).created_at.utcoffset() == timedelta(0)


def test_unicode_titles_round_trip(repo):
    t = add(repo, "గృహపాఠం 📚 café")
    assert repo.get(t.id).title == "గృహపాఠం 📚 café"


def test_update_of_a_missing_task_changes_nothing(repo):
    t = add(repo, "a")
    ghost = t.completed(T0)
    ghost = type(ghost)(id=77, title="x", done=True, created_at=T0, completed_at=T0)
    repo.update(ghost)
    assert repo.get(77) is None and len(repo.list()) == 1


# ---------- things only SQLite has: its own rules and its own safety ----------

def raw(repo):
    return closing(sqlite3.connect(repo._path))


def test_sqlite_has_a_unique_index_on_the_key(sqlite_repo):
    with raw(sqlite_repo) as conn:
        indexes = conn.execute("PRAGMA index_list(tasks)").fetchall()
        unique_cols = [conn.execute(f"PRAGMA index_info({i[1]})").fetchall()[0][2] for i in indexes if i[2] == 1]
    assert "title_key" in unique_cols


def test_the_database_itself_refuses_a_duplicate_even_without_the_app(sqlite_repo):
    add(sqlite_repo, "Quiz")
    with raw(sqlite_repo) as conn, pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute("INSERT INTO tasks (title, title_key, created_at) VALUES ('x', 'quiz', 'now')")


def test_the_database_refuses_a_done_task_without_a_time(sqlite_repo):
    t = add(sqlite_repo, "a")
    with raw(sqlite_repo) as conn, pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (t.id,))


def test_the_database_refuses_an_open_task_with_a_time(sqlite_repo):
    t = add(sqlite_repo, "a")
    with raw(sqlite_repo) as conn, pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("UPDATE tasks SET completed_at = 'x' WHERE id = ?", (t.id,))


def test_the_database_refuses_done_values_other_than_0_and_1(sqlite_repo):
    t = add(sqlite_repo, "a")
    with raw(sqlite_repo) as conn, pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("UPDATE tasks SET done = 2, completed_at = 'x' WHERE id = ?", (t.id,))


def test_sql_in_a_title_is_stored_as_plain_text(sqlite_repo):
    nasty = "x'); DROP TABLE tasks;--"
    t = add(sqlite_repo, nasty)
    assert sqlite_repo.get(t.id).title == nasty
    assert sqlite_repo.find_by_key(title_key(nasty)).id == t.id
    assert len(sqlite_repo.list()) == 1  # the table is still there


def test_data_survives_a_new_repository_object(tmp_path):
    first = SqliteTaskRepository(tmp_path / "keep.db")
    first.init_schema()
    t = add(first, "keep me")
    second = SqliteTaskRepository(tmp_path / "keep.db")
    second.init_schema()  # running it again must not wipe anything
    assert second.get(t.id) == t


def test_two_threads_inserting_the_same_key_leave_one_row(sqlite_repo):
    barrier = threading.Barrier(8, timeout=5)
    outcomes = []

    def go():
        barrier.wait()
        try:
            add(sqlite_repo, "Same")
            outcomes.append("ok")
        except DuplicateTitle:
            outcomes.append("dup")

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes) == ["dup"] * 7 + ["ok"]
    assert len(sqlite_repo.list()) == 1


def test_service_over_sqlite_catches_the_race_the_friendly_check_misses(sqlite_repo):
    """Same barrier trick as the service test, but with the REAL database: this proves the UNIQUE index, not just the idea."""
    barrier = threading.Barrier(2, timeout=5)
    real_find = sqlite_repo.find_by_key

    def blind_find(key):
        found = real_find(key)
        barrier.wait()
        return found

    sqlite_repo.find_by_key = blind_find
    service = TaskService(sqlite_repo, 100)
    results = []

    def attempt():
        try:
            results.append(service.create("Same title"))
        except DuplicateTitle as error:
            results.append(error)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(type(r).__name__ for r in results) == ["DuplicateTitle", "Task"]
    assert 'There is already a task called "Same title"' in [str(r) for r in results if isinstance(r, DuplicateTitle)][0]
    assert len(sqlite_repo.list()) == 1


def test_a_non_unique_integrity_error_is_not_called_a_duplicate(sqlite_repo):
    """Only the UNIQUE failure means 'duplicate'. Anything else must stay a loud error."""
    with pytest.raises(sqlite3.IntegrityError):
        sqlite_repo.add(None, "k", T0)  # title NOT NULL fails
```

### `tests/test_api.py`

```python
import pytest


def make(client, title="Math homework"):
    return client.post("/tasks", json={"title": title})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_returns_201_and_the_task(client, clock):
    r = make(client, "  Math   homework ")
    assert r.status_code == 201
    body = r.json()
    assert body == {"id": 1, "title": "Math homework", "done": False, "created_at": "2026-01-01T09:00:00Z", "completed_at": None}


def test_list_empty_then_filled(client):
    assert client.get("/tasks").json() == []
    make(client, "a"), make(client, "b")
    assert [t["title"] for t in client.get("/tasks").json()] == ["a", "b"]


def test_complete_and_reopen_round_trip(client, clock):
    make(client)
    done = client.post("/tasks/1/complete")
    assert done.status_code == 200 and done.json()["done"] is True and done.json()["completed_at"] == "2026-01-01T09:00:00Z"
    back = client.post("/tasks/1/reopen")
    assert back.status_code == 200 and back.json()["done"] is False and back.json()["completed_at"] is None


def test_complete_is_idempotent_over_http(client, clock):
    make(client)
    first = client.post("/tasks/1/complete").json()
    clock.advance(hours=5)
    assert client.post("/tasks/1/complete").json() == first


def test_filter_done(client):
    make(client, "a"), make(client, "b")
    client.post("/tasks/1/complete")
    assert [t["title"] for t in client.get("/tasks?done=true").json()] == ["a"]
    assert [t["title"] for t in client.get("/tasks?done=false").json()] == ["b"]


def test_duplicate_gives_409(client):
    make(client, "Quiz")
    r = make(client, "QUIZ")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_title"
    assert len(client.get("/tasks").json()) == 1


@pytest.mark.parametrize("title", ["", "   ", "\u200b", "x" * 101, "a\x00b"])
def test_bad_titles_give_422_with_a_reason(client, title):
    r = make(client, title)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_title"
    assert client.get("/tasks").json() == []


@pytest.mark.parametrize(
    "payload",
    [{}, {"title": None}, {"title": 5}, {"title": ["a"]}, {"title": "ok", "done": True}, {"titel": "typo"}, []],
)
def test_wrong_shapes_give_422_invalid_request(client, payload):
    r = client.post("/tasks", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"
    assert client.get("/tasks").json() == []


def test_body_that_is_not_json_gives_422(client):
    r = client.post("/tasks", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["error"]["fields"][0]["field"] == "body"


def test_missing_body_gives_422(client):
    assert client.post("/tasks").status_code == 422


def test_validation_answer_never_echoes_the_input(client):
    secret = "SuperSecretValue12345"
    r = client.post("/tasks", json={"title": 5, "password": secret})
    assert secret not in r.text


def test_unknown_task_gives_404(client):
    for path in ("/tasks/42/complete", "/tasks/42/reopen"):
        r = client.post(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "task_not_found"


@pytest.mark.parametrize("task_id", ["abc", "0", "-1", "1.5", "99999999999999999999", "9223372036854775808"])
def test_bad_ids_give_422_not_a_crash(client, task_id):
    assert client.post(f"/tasks/{task_id}/complete").status_code == 422


def test_biggest_possible_id_is_a_clean_404(client):
    assert client.post(f"/tasks/{2**63 - 1}/complete").status_code == 404


def test_bad_filter_value_gives_422(client):
    assert client.get("/tasks?done=maybe").status_code == 422


def test_unknown_address_and_wrong_method(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.delete("/tasks")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed" and "allow" in r.headers


def test_every_error_has_the_same_shape(client):
    make(client, "Quiz")
    answers = [make(client, "quiz"), make(client, ""), client.post("/tasks/9/complete"), client.get("/nope"), client.post("/tasks", json=[])]
    for r in answers:
        assert list(r.json()) == ["error"]
        assert {"code", "message", "request_id"} <= set(r.json()["error"])
        assert r.json()["error"]["request_id"] == r.headers["x-request-id"]


def test_titles_with_html_or_sql_are_stored_as_text(client):
    r = make(client, "<script>alert(1)</script>")
    assert r.status_code == 201 and r.json()["title"] == "<script>alert(1)</script>"
    r = make(client, "'; DROP TABLE tasks; --")
    assert r.status_code == 201 and len(client.get("/tasks").json()) == 2


def test_the_openapi_page_lists_the_four_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/tasks"]) == {"get", "post"}
    assert "/tasks/{task_id}/complete" in paths and "/tasks/{task_id}/reopen" in paths
```

### `tests/test_errors.py`

```python
"""Errors are mapped to status codes in ONE place. These tests keep it that way."""
import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.domain.errors as domain_errors
import app.api.routes as routes
from app.api.errors import STATUS_FOR_ERROR
from app.domain.errors import TaskError
from app.main import create_app
from app.repositories.memory import InMemoryTaskRepository

from tests.conftest import log_lines

API = Path(routes.__file__).parent


def all_task_errors():
    return [c for _, c in inspect.getmembers(domain_errors, inspect.isclass) if issubclass(c, TaskError) and c is not TaskError]


def test_every_domain_error_has_a_status_code():
    missing = [c.__name__ for c in all_task_errors() if c not in STATUS_FOR_ERROR]
    assert missing == []


def test_the_table_only_holds_real_client_errors():
    assert set(STATUS_FOR_ERROR.values()) <= {400, 404, 409, 422}
    assert STATUS_FOR_ERROR.keys() <= set(all_task_errors())


def test_routes_and_service_never_choose_a_status_code_for_an_error():
    """The status numbers and HTTPException belong in api/errors.py only."""
    for path in [API / "routes.py", API / "deps.py", API / "schemas.py", API.parent / "services" / "tasks.py"]:
        text = path.read_text()
        assert "HTTPException" not in text, path.name
        assert not re.search(r"status_code\s*=\s*4\d\d", text), path.name
        assert not re.search(r"\b(40[0-9]|422)\b", re.sub(r"#.*", "", text)), path.name


def test_a_new_unmapped_error_answers_500_and_is_logged(settings, log_stream):
    class Surprise(TaskError):
        code = "surprise"

    class Boom(InMemoryTaskRepository):
        def list(self, done=None):
            raise Surprise("not mapped")

    client = TestClient(create_app(settings, log_stream=log_stream, repository=Boom()), raise_server_exceptions=False)
    r = client.get("/tasks")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert any("no status code" in line["message"] for line in log_lines(log_stream))


class Exploding(InMemoryTaskRepository):
    def list(self, done=None):
        raise RuntimeError("disk on fire /secret/path")


@pytest.fixture
def broken_client(settings, log_stream):
    return TestClient(create_app(settings, log_stream=log_stream, repository=Exploding()), raise_server_exceptions=False)


def test_unexpected_error_gives_500_without_leaking_details(broken_client):
    r = broken_client.get("/tasks")
    assert r.status_code == 500
    assert "disk on fire" not in r.text and "secret" not in r.text and "Traceback" not in r.text
    assert r.json()["error"]["code"] == "internal_error"


def test_500_still_carries_the_request_id_in_body_and_header(broken_client):
    r = broken_client.get("/tasks", headers={"X-Request-ID": "my-id-500"})
    assert r.headers["x-request-id"] == "my-id-500" == r.json()["error"]["request_id"]


def test_500_is_logged_with_the_traceback_and_the_same_request_id(broken_client, log_stream):
    broken_client.get("/tasks", headers={"X-Request-ID": "my-id-500"})
    lines = log_lines(log_stream)
    error = [l for l in lines if l["level"] == "ERROR"]
    assert len(error) == 1 and "disk on fire" in error[0]["exception"] and error[0]["request_id"] == "my-id-500"
    assert all(l["request_id"] == "my-id-500" for l in lines)
    assert [l["status"] for l in lines if l["logger"] == "classtasks.access"] == [500]
```

### `tests/test_logging.py`

```python
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app.logging_setup import configure_logging
from tests.conftest import log_lines


def test_every_line_is_json_with_the_basic_fields(client, log_stream):
    client.post("/tasks", json={"title": "a"})
    lines = log_lines(log_stream)
    assert lines
    for line in lines:
        assert {"ts", "level", "logger", "message", "request_id"} <= set(line)
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", line["ts"])


def test_one_request_id_on_every_line_of_a_request_across_all_three_layers(client, log_stream):
    r = client.post("/tasks", json={"title": "a"})
    lines = log_lines(log_stream)
    assert {l["logger"] for l in lines} == {"classtasks.repository", "classtasks.service", "classtasks.access"}
    assert {l["request_id"] for l in lines} == {r.headers["x-request-id"]}


def test_different_requests_get_different_ids(client, log_stream):
    ids = {client.get("/tasks").headers["x-request-id"] for _ in range(10)}
    assert len(ids) == 10 and all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids)


def test_a_safe_incoming_id_is_kept_everywhere(client, log_stream):
    r = client.post("/tasks", json={"title": "a"}, headers={"X-Request-ID": "trace-123.abc_X"})
    assert r.headers["x-request-id"] == "trace-123.abc_X"
    assert {l["request_id"] for l in log_lines(log_stream)} == {"trace-123.abc_X"}


@pytest.mark.parametrize("bad", ["has space", "semi;colon", "x" * 65, "new\nline"[:8], "quote\"x", "<script>", "ünï", ""])
def test_an_unsafe_incoming_id_is_replaced(client, log_stream, bad):
    try:
        r = client.get("/tasks", headers={"X-Request-ID": bad})
    except Exception:  # some strings cannot even be sent as a header: then there is nothing to protect
        return
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-request-id"])
    assert all(l["request_id"] == r.headers["x-request-id"] for l in log_lines(log_stream))


def test_a_64_character_id_is_still_accepted(client):
    assert client.get("/tasks", headers={"X-Request-ID": "a" * 64}).headers["x-request-id"] == "a" * 64


@pytest.mark.parametrize("call", [
    lambda c: c.get("/tasks"),
    lambda c: c.post("/tasks", json={"title": "a"}),
    lambda c: c.post("/tasks", json={"title": ""}),
    lambda c: c.post("/tasks", json=[]),
    lambda c: c.post("/tasks/9/complete"),
    lambda c: c.get("/nope"),
    lambda c: c.delete("/tasks"),
])
def test_the_header_is_on_every_kind_of_answer(client, call):
    r = call(client)
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-request-id"])


def test_error_lines_carry_the_id_too(client, log_stream):
    client.post("/tasks", json={"title": "Quiz"})
    log_stream.truncate(0), log_stream.seek(0)
    r = client.post("/tasks", json={"title": "quiz"})
    lines = log_lines(log_stream)
    assert lines and {l["request_id"] for l in lines} == {r.headers["x-request-id"]}


def test_access_line_has_method_path_status_and_duration(client, log_stream):
    client.post("/tasks/7/complete")
    access = [l for l in log_lines(log_stream) if l["logger"] == "classtasks.access"][0]
    assert (access["method"], access["path"], access["status"]) == ("POST", "/tasks/7/complete", 404)
    assert isinstance(access["duration_ms"], (int, float)) and access["duration_ms"] >= 0


def test_the_query_string_is_not_logged(client, log_stream):
    client.get("/tasks?done=true&token=SECRET123")
    assert "SECRET123" not in log_stream.getvalue()


def test_task_titles_are_not_logged(client, log_stream):
    client.post("/tasks", json={"title": "my private plan"})
    assert "private" not in log_stream.getvalue()


def test_the_service_line_names_the_task_id(client, log_stream):
    client.post("/tasks", json={"title": "a"})
    created = [l for l in log_lines(log_stream) if l["message"] == "task created"][0]
    assert created["task_id"] == 1 and created["level"] == "INFO"


def test_lines_outside_a_request_have_a_null_id(log_stream):
    configure_logging("INFO", log_stream)
    logging.getLogger("classtasks.service").info("startup")
    assert log_lines(log_stream)[0]["request_id"] is None


def test_log_level_filters_lines(settings, log_stream):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from app.main import create_app
    quiet = TestClient(create_app(replace(settings, log_level="WARNING"), log_stream=log_stream))
    quiet.post("/tasks", json={"title": "a"})
    assert log_stream.getvalue() == ""
    loud = TestClient(create_app(replace(settings, log_level="DEBUG", database_url=settings.database_url + "2"), log_stream=log_stream))
    loud.post("/tasks", json={"title": "a"})
    assert any(l["level"] == "DEBUG" for l in log_lines(log_stream))


def test_configure_logging_twice_does_not_print_every_line_twice(log_stream):
    configure_logging("INFO", log_stream)
    configure_logging("INFO", log_stream)
    logging.getLogger("classtasks.service").info("once")
    assert len(log_lines(log_stream)) == 1


def test_a_line_with_a_newline_in_the_message_is_still_one_line(log_stream):
    configure_logging("INFO", log_stream)
    logging.getLogger("classtasks.service").info("a\nb\r\nc")
    assert len(log_stream.getvalue().splitlines()) == 1
    assert log_lines(log_stream)[0]["message"] == "a\nb\r\nc"


def test_ids_do_not_mix_when_many_requests_run_at_once(live_server):
    """40 requests at the same time, each with its own id. Every 'task created' line must carry the id of the request that got that task."""
    def one(i):
        r = httpx.post(f"{live_server.base_url}/tasks", json={"title": f"task {i}"}, headers={"X-Request-ID": f"req-{i}"})
        return r.json()["id"], r.headers["x-request-id"]

    with ThreadPoolExecutor(max_workers=20) as pool:
        answers = list(pool.map(one, range(40)))
    assert len({a[0] for a in answers}) == 40
    created = {l["task_id"]: l["request_id"] for l in log_lines(live_server.stream) if l["message"] == "task created"}
    assert created == {task_id: rid for task_id, rid in answers}
    # and every single line belongs to one of the 40 requests
    assert {l["request_id"] for l in log_lines(live_server.stream)} == {f"req-{i}" for i in range(40)}


@pytest.mark.parametrize("bad", ["a\nb", "a\r\nInjected: yes", "tab\tid", "x" * 65, "", None, "é", "a b", "../../etc", "id\x00"])
def test_pick_request_id_replaces_anything_unsafe(bad):
    from app.api.middleware import pick_request_id
    assert re.fullmatch(r"[0-9a-f]{32}", pick_request_id(bad))


@pytest.mark.parametrize("good", ["a", "abc-123", "A.b_c-9", "x" * 64])
def test_pick_request_id_keeps_safe_ids(good):
    from app.api.middleware import pick_request_id
    assert pick_request_id(good) == good
```

### `tests/test_settings.py`

```python
import os
import subprocess
import socket
import sys
import time
from pathlib import Path

import httpx
import pytest

from app.main import create_app
from app.settings import KNOWN_KEYS, Settings, SettingsError, StartupError, parse_env_text, read_env_file

ROOT = Path(__file__).resolve().parent.parent


def load(env=None, file_text=None, tmp=None):
    path = None
    if file_text is not None:
        path = tmp / ".env"
        path.write_text(file_text)
    return Settings.load(environ=env or {}, env_file=path)


def test_defaults_when_nothing_is_set(tmp_path):
    s = load({}, tmp=tmp_path)
    assert (s.database_url, s.max_title_length, s.log_level, s.port) == ("sqlite:///./class_tasks.db", 100, "INFO", 8000)


def test_environment_values_are_used(tmp_path):
    s = load({"APP_MAX_TITLE_LENGTH": "40", "APP_LOG_LEVEL": "debug", "APP_PORT": "9000", "APP_DATABASE_URL": "sqlite:///x/y.db"}, tmp=tmp_path)
    assert (s.max_title_length, s.log_level, s.port, s.database_path) == (40, "DEBUG", 9000, "x/y.db")


def test_values_are_trimmed(tmp_path):
    assert load({"APP_MAX_TITLE_LENGTH": "  25 "}, tmp=tmp_path).max_title_length == 25


@pytest.mark.parametrize("value", ["abc", "1.5", "-3", "+5", "1e3", "1_0", "١٢", "ten", "0x10", "5 5"])
def test_max_title_length_must_be_digits(value, tmp_path):
    with pytest.raises(SettingsError) as e:
        load({"APP_MAX_TITLE_LENGTH": value}, tmp=tmp_path)
    assert "APP_MAX_TITLE_LENGTH" in str(e.value) and "whole number" in str(e.value) and repr(value.strip()) in str(e.value)


@pytest.mark.parametrize("value", ["0", "501", "99999"])
def test_max_title_length_range(value, tmp_path):
    with pytest.raises(SettingsError, match="from 1 to 500"):
        load({"APP_MAX_TITLE_LENGTH": value}, tmp=tmp_path)


@pytest.mark.parametrize("value", ["1", "500"])
def test_max_title_length_edges_are_allowed(value, tmp_path):
    assert load({"APP_MAX_TITLE_LENGTH": value}, tmp=tmp_path).max_title_length == int(value)


@pytest.mark.parametrize("value", ["0", "65536", "abc", "-1"])
def test_port_must_be_valid(value, tmp_path):
    with pytest.raises(SettingsError, match="APP_PORT"):
        load({"APP_PORT": value}, tmp=tmp_path)


@pytest.mark.parametrize("value", ["LOUD", "10", "TRACE", "critical"])
def test_log_level_must_be_known(value, tmp_path):
    with pytest.raises(SettingsError, match="APP_LOG_LEVEL"):
        load({"APP_LOG_LEVEL": value}, tmp=tmp_path)


@pytest.mark.parametrize("value", ["postgres://u@h/db", "tasks.db", "sqlite://tasks.db", "sqlite:///", "sqlite:///:memory:", "http://x"])
def test_database_url_must_be_a_sqlite_file(value, tmp_path):
    with pytest.raises(SettingsError, match="APP_DATABASE_URL"):
        load({"APP_DATABASE_URL": value}, tmp=tmp_path)


def test_an_empty_value_is_an_error_not_a_silent_default(tmp_path):
    with pytest.raises(SettingsError, match="set but empty"):
        load({"APP_PORT": ""}, tmp=tmp_path)


def test_all_problems_are_reported_together(tmp_path):
    with pytest.raises(SettingsError) as e:
        load({"APP_MAX_TITLE_LENGTH": "abc", "APP_PORT": "0", "APP_LOG_LEVEL": "LOUD"}, tmp=tmp_path)
    text = str(e.value)
    assert "APP_MAX_TITLE_LENGTH" in text and "APP_PORT" in text and "APP_LOG_LEVEL" in text


def test_the_error_names_what_to_do(tmp_path):
    with pytest.raises(SettingsError) as e:
        load({"APP_MAX_TITLE_LENGTH": "abc"}, tmp=tmp_path)
    assert "Use digits only, for example 100" in str(e.value)


def test_unrelated_environment_variables_are_ignored(tmp_path):
    assert load({"PATH": "/bin", "APP_ID": "x", "APPDATA": "y"}, tmp=tmp_path).port == 8000


# ---------- the .env file ----------

def test_env_file_values_are_used(tmp_path):
    s = load({}, "APP_MAX_TITLE_LENGTH=30\nAPP_LOG_LEVEL=WARNING\n", tmp_path)
    assert (s.max_title_length, s.log_level) == (30, "WARNING")


def test_real_environment_beats_the_env_file(tmp_path):
    s = load({"APP_MAX_TITLE_LENGTH": "10"}, "APP_MAX_TITLE_LENGTH=30\n", tmp_path)
    assert s.max_title_length == 10


def test_a_bad_value_in_the_env_file_stops_loading(tmp_path):
    with pytest.raises(SettingsError, match="APP_MAX_TITLE_LENGTH='abc'"):
        load({}, "APP_MAX_TITLE_LENGTH=abc\n", tmp_path)


def test_a_missing_env_file_is_fine(tmp_path):
    assert Settings.load(environ={}, env_file=tmp_path / "nope.env").port == 8000


def test_env_file_comments_quotes_and_blank_lines():
    text = '# comment\n\nAPP_PORT=9000   # trailing comment\nAPP_DATABASE_URL="sqlite:///a b/c.db"\nAPP_LOG_LEVEL=\'DEBUG\'\n  export APP_MAX_TITLE_LENGTH = 7\n'
    assert parse_env_text(text) == {"APP_PORT": "9000", "APP_DATABASE_URL": "sqlite:///a b/c.db", "APP_LOG_LEVEL": "DEBUG", "APP_MAX_TITLE_LENGTH": "7"}


def test_a_hash_inside_a_value_without_a_space_is_kept():
    assert parse_env_text("APP_DATABASE_URL=sqlite:///a#b.db")["APP_DATABASE_URL"] == "sqlite:///a#b.db"


def test_malformed_lines_are_reported_with_their_numbers():
    with pytest.raises(SettingsError) as e:
        parse_env_text("APP_PORT=1\nthis is not valid\n=oops\nOK=1\n")
    assert "line 2" in str(e.value) and "line 3" in str(e.value) and "line 4" not in str(e.value)


def test_duplicate_keys_in_the_env_file_are_an_error():
    with pytest.raises(SettingsError, match="line 3: APP_PORT is already set on line 1"):
        parse_env_text("APP_PORT=1\nOTHER=2\nAPP_PORT=3\n")


def test_a_typo_in_the_env_file_is_caught_with_a_hint(tmp_path):
    with pytest.raises(SettingsError) as e:
        load({}, "APP_MAX_TITLE_LEN=5\n", tmp_path)
    assert "APP_MAX_TITLE_LEN" in str(e.value) and "Did you mean APP_MAX_TITLE_LENGTH" in str(e.value)


def test_env_example_is_valid_and_matches_the_defaults(tmp_path):
    s = Settings.load(environ={}, env_file=ROOT / ".env.example")
    assert s == Settings()


def test_env_example_documents_every_setting_and_nothing_else():
    keys = set(read_env_file(ROOT / ".env.example"))
    assert keys == set(KNOWN_KEYS)
    assert set(Settings.__dataclass_fields__) == {"database_url", "max_title_length", "log_level", "port"}


def test_env_file_is_ignored_by_git():
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()
    assert ".env.example" not in (ROOT / ".gitignore").read_text().splitlines()


# ---------- stopping at start-up ----------

def test_create_app_refuses_bad_settings_object_via_load(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MAX_TITLE_LENGTH", "abc")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SettingsError):
        create_app()


def test_create_app_refuses_an_unopenable_database(tmp_path):
    with pytest.raises(StartupError, match="Cannot open the database"):
        create_app(Settings(database_url=f"sqlite:///{tmp_path}/no/such/dir/x.db"))


def run_app(env_extra, cwd, timeout=20):
    env = {**os.environ, "PYTHONPATH": str(ROOT), **env_extra}
    for key in KNOWN_KEYS:
        if key not in env_extra:
            env.pop(key, None)
    return subprocess.run([sys.executable, "-m", "app"], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def test_bad_setting_stops_the_real_process_before_it_listens(tmp_path):
    t0 = time.time()
    r = run_app({"APP_MAX_TITLE_LENGTH": "abc"}, tmp_path)
    assert r.returncode == 2 and time.time() - t0 < 10
    assert "Cannot start" in r.stderr and "APP_MAX_TITLE_LENGTH='abc'" in r.stderr
    assert "Traceback" not in r.stderr and "Uvicorn running" not in r.stderr + r.stdout


def test_bad_value_in_a_real_env_file_stops_the_real_process(tmp_path):
    (tmp_path / ".env").write_text("APP_PORT=nope\n")
    r = run_app({}, tmp_path)
    assert r.returncode == 2 and "APP_PORT='nope'" in r.stderr


def test_unopenable_database_stops_the_real_process(tmp_path):
    r = run_app({"APP_DATABASE_URL": f"sqlite:///{tmp_path}/missing/x.db"}, tmp_path)
    assert r.returncode == 2 and "Cannot open the database" in r.stderr


def test_good_settings_start_a_real_process_that_answers(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "APP_PORT": str(port), "APP_DATABASE_URL": f"sqlite:///{tmp_path}/p.db", "APP_LOG_LEVEL": "INFO"}
    proc = subprocess.Popen([sys.executable, "-m", "app"], cwd=tmp_path, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            pytest.fail("server never answered")
        r = httpx.post(f"http://127.0.0.1:{port}/tasks", json={"title": "from a real process"})
        assert r.status_code == 201
    finally:
        proc.terminate()
        out, err = proc.communicate(timeout=10)
    import json
    json_lines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert any(l["message"] == "task created" and l["request_id"] == r.headers["x-request-id"] for l in json_lines)
    assert '"GET /health HTTP/1.1"' not in out + err and '"POST /tasks HTTP/1.1"' not in out + err  # uvicorn's own access log is off
```

### `tests/test_concurrency.py`

```python
"""Two requests at the same time must never make two rows. Run against a REAL server."""
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx


def post_together(base_url, titles):
    barrier = threading.Barrier(len(titles), timeout=10)

    def go(title):
        barrier.wait()  # release every request at the same instant
        return httpx.post(f"{base_url}/tasks", json={"title": title}, timeout=30)

    with ThreadPoolExecutor(max_workers=len(titles)) as pool:
        return list(pool.map(go, titles))


def test_two_requests_with_the_same_title_make_one_row(live_server):
    answers = post_together(live_server.base_url, ["Same title"] * 2)
    assert sorted(a.status_code for a in answers) == [201, 409]
    assert len(httpx.get(f"{live_server.base_url}/tasks").json()) == 1


def test_thirty_requests_with_the_same_title_make_one_row(live_server):
    answers = post_together(live_server.base_url, ["Same title"] * 30)
    codes = sorted(a.status_code for a in answers)
    assert codes == [201] + [409] * 29
    assert len(httpx.get(f"{live_server.base_url}/tasks").json()) == 1


def test_same_title_in_different_spelling_at_the_same_time_makes_one_row(live_server):
    answers = post_together(live_server.base_url, ["Quiz", "QUIZ", " quiz ", "Quiz  "] * 5)
    assert sorted(a.status_code for a in answers) == [201] + [409] * 19
    assert len(httpx.get(f"{live_server.base_url}/tasks").json()) == 1


def test_different_titles_at_the_same_time_all_succeed_with_distinct_ids(live_server):
    answers = post_together(live_server.base_url, [f"task {i}" for i in range(30)])
    assert all(a.status_code == 201 for a in answers)
    assert sorted(a.json()["id"] for a in answers) == list(range(1, 31))


def test_completing_the_same_task_at_the_same_time_is_harmless(live_server):
    task = httpx.post(f"{live_server.base_url}/tasks", json={"title": "a"}).json()
    barrier = threading.Barrier(10, timeout=10)

    def go(_):
        barrier.wait()
        return httpx.post(f"{live_server.base_url}/tasks/{task['id']}/complete", timeout=30)

    with ThreadPoolExecutor(max_workers=10) as pool:
        answers = list(pool.map(go, range(10)))
    assert all(a.status_code == 200 for a in answers)
    assert len({a.json()["completed_at"] for a in answers}) <= 10  # all succeeded; the stored task is done
    final = httpx.get(f"{live_server.base_url}/tasks?done=true").json()
    assert len(final) == 1 and final[0]["done"] and final[0]["completed_at"]
```

### `tests/test_layers.py`

```python
"""Layer test: each layer may import only what it is allowed to. Reads the real source files (no running needed).
Breaks on purpose when, say, the service imports fastapi or the api imports sqlite3."""
import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
STDLIB = set(sys.stdlib_module_names)

# layer -> (third-party packages allowed, app modules allowed, standard-library modules NOT allowed)
RULES = {
    "domain": (set(), {"app.domain"}, {"sqlite3", "http", "socket", "urllib", "asyncio", "threading"}),
    "services": (set(), {"app.domain", "app.services"}, {"sqlite3", "http", "socket", "urllib"}),
    "repositories": (set(), {"app.domain", "app.repositories"}, {"http", "socket", "urllib"}),
    "api": ({"fastapi", "starlette", "pydantic"}, {"app.domain", "app.services", "app.api", "app.request_context"}, {"sqlite3"}),
    "support": (set(), {"app.request_context", "app.settings"}, {"sqlite3"}),  # settings, logging_setup, request_context
}
MAIN_FILES = {"main.py", "__main__.py"}  # the wiring: allowed to know everything


def imported_modules(source: str) -> list[tuple[str, int]]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.level if hasattr(node, "level") else 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((("." * node.level) + (node.module or ""), node.level))
    return found


def find_violations(source: str, layer: str) -> list[str]:
    third_party, app_ok, stdlib_banned = RULES[layer]
    problems = []
    for name, level in imported_modules(source):
        if level >= 1:
            problems.append(f"relative import {name!r}: use absolute imports so layers can be checked")
            continue
        top = name.split(".")[0]
        if top == "app":
            if not any(name == ok or name.startswith(ok + ".") for ok in app_ok):
                problems.append(f"{layer} must not import {name}")
        elif top in STDLIB:
            if top in stdlib_banned:
                problems.append(f"{layer} must not import {name}")
        elif top not in third_party:
            problems.append(f"{layer} must not import {name}")
    return problems


def layer_of(path: Path) -> str | None:
    rel = path.relative_to(APP)
    if rel.name in MAIN_FILES:
        return None
    return rel.parts[0] if len(rel.parts) > 1 else "support"


def source_files():
    return [p for p in sorted(APP.rglob("*.py")) if layer_of(p)]


def test_the_scan_really_sees_all_the_layers():
    layers = {layer_of(p) for p in source_files()}
    assert layers == {"domain", "services", "repositories", "api", "support"}
    assert len(source_files()) >= 18


@pytest.mark.parametrize("path", source_files(), ids=lambda p: str(p.relative_to(APP)))
def test_each_file_imports_only_what_its_layer_allows(path):
    assert find_violations(path.read_text(), layer_of(path)) == []


def test_main_files_are_the_only_ones_exempt():
    assert {p.name for p in APP.rglob("*.py") if layer_of(p) is None} == MAIN_FILES


# ---------- the checker itself: does it notice a bad import? ----------

@pytest.mark.parametrize("source,layer", [
    ("import fastapi", "services"),
    ("from fastapi import HTTPException", "services"),
    ("from starlette.requests import Request", "services"),
    ("from pydantic import BaseModel", "domain"),
    ("import sqlite3", "services"),
    ("import sqlite3", "domain"),
    ("import sqlite3", "api"),
    ("from app.repositories.sqlite import SqliteTaskRepository", "api"),
    ("from app.repositories.sqlite import SqliteTaskRepository", "services"),
    ("from app.api.routes import build_router", "services"),
    ("from app.services.tasks import TaskService", "domain"),
    ("from app.services.tasks import TaskService", "repositories"),
    ("from app.api.errors import STATUS_FOR_ERROR", "repositories"),
    ("import requests", "services"),
    ("from ..domain import task", "services"),
    ("from . import x", "api"),
    ("def f():\n    import fastapi", "services"),
    ("import os\nimport fastapi.exceptions", "domain"),
    ("import sqlite3", "support"),
    ("import fastapi", "support"),
])
def test_the_checker_catches_a_forbidden_import(source, layer):
    assert find_violations(source, layer) != []


@pytest.mark.parametrize("source,layer", [
    ("from app.domain.task import Task\nimport logging\nfrom datetime import datetime", "services"),
    ("from app.domain.errors import TaskError", "domain"),
    ("import sqlite3\nfrom app.domain.task import Task", "repositories"),
    ("from fastapi import APIRouter\nfrom app.services.tasks import TaskService", "api"),
    ("import logging\nfrom app.request_context import request_id_var", "support"),
])
def test_the_checker_allows_what_the_layer_may_use(source, layer):
    assert find_violations(source, layer) == []
```

### `tests/test_before_vs_after.py`

```python
"""The refactor must not change what a user sees. The same black-box checks run against the 'before' app and the new app.
(The new app adds things the 'before' never had: case-insensitive titles, timestamps, request ids, JSON errors. Those are tested elsewhere.)"""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture(params=["before", "after"])
def api(request, tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'ba.db'}"
    if request.param == "before":
        monkeypatch.setenv("APP_DATABASE_URL", url)
        from before.before_app import app as before_app
        return TestClient(before_app, raise_server_exceptions=False)
    return TestClient(create_app(Settings(database_url=url)), raise_server_exceptions=False)


def small(body):
    return {k: body[k] for k in ("id", "title", "done")}


def test_create_and_list(api):
    r = api.post("/tasks", json={"title": "Math homework"})
    assert r.status_code == 201 and small(r.json()) == {"id": 1, "title": "Math homework", "done": False}
    assert [small(t) for t in api.get("/tasks").json()] == [{"id": 1, "title": "Math homework", "done": False}]


def test_title_is_trimmed(api):
    assert api.post("/tasks", json={"title": "  Quiz  "}).json()["title"] == "Quiz"


def test_duplicate_gives_409(api):
    api.post("/tasks", json={"title": "Quiz"})
    assert api.post("/tasks", json={"title": "Quiz"}).status_code == 409
    assert len(api.get("/tasks").json()) == 1


@pytest.mark.parametrize("title", ["", "   ", "x" * 101])
def test_bad_title_gives_422(api, title):
    assert api.post("/tasks", json={"title": title}).status_code == 422


def test_complete_and_reopen(api):
    api.post("/tasks", json={"title": "a"})
    assert small(api.post("/tasks/1/complete").json()) == {"id": 1, "title": "a", "done": True}
    assert small(api.post("/tasks/1/reopen").json()) == {"id": 1, "title": "a", "done": False}


def test_unknown_task_gives_404(api):
    assert api.post("/tasks/5/complete").status_code == 404
    assert api.post("/tasks/5/reopen").status_code == 404


def test_before_has_the_gaps_the_refactor_closes(tmp_path, monkeypatch):
    """What the 'before' got wrong, written down as facts so the 'after' is not just a feeling."""
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'gap.db'}")
    from before.before_app import app as before_app
    c = TestClient(before_app, raise_server_exceptions=False)
    c.post("/tasks", json={"title": "Quiz"})
    assert c.post("/tasks", json={"title": "QUIZ"}).status_code == 201  # no case-insensitive rule
    assert "created_at" not in c.get("/tasks").json()[0]  # no timestamps
    assert "x-request-id" not in c.get("/tasks").headers  # no request id
    import sqlite3
    with sqlite3.connect(tmp_path / "gap.db") as conn:
        indexes = conn.execute("PRAGMA index_list(tasks)").fetchall()
    assert not [i for i in indexes if i[2] == 1 and "title" in i[1]]  # no unique rule in the database
```

---

## 8. Results

| Check | Command | Result |
|---|---|---|
| All tests | `python -m pytest -q` | **286 passed** in about 6 seconds (run 5 times in a row: always 286), with one harmless warning: Starlette says its test client now prefers `httpx2` over `httpx` |
| Break it on purpose | `python break46.py` | **64 of 64** deliberate mistakes caught |
| Two requests, same title | `test_concurrency.py` (real server) | 1 created, 1 refused, 1 row. 30 at once: 1 created, 29 refused, 1 row |
| The race, before and after | `python scripts/race_demo.py` (40 requests at once, 5 rounds) | Before: rows made per round `[1, 16, 3, 1, 1]` and, in a second run, `[1, 1, 2, 1, 1]` (should be 1 each). After: `[1, 1, 1, 1, 1]` both times |
| Bad setting at start-up | `APP_MAX_TITLE_LENGTH=abc APP_PORT=0 python -m app` | Prints both problems in plain words, **exit code 2**, nothing listens |
| Typo in the .env file | `APP_MAX_TITLE_LEN=5` in `.env`, then `python -m app` | `APP_MAX_TITLE_LEN in the .env file is not a setting this app knows. Did you mean APP_MAX_TITLE_LENGTH?`, exit code 2 |
| Request id on every line | `test_logging.py`, one POST | 3 lines (repository, service, access) with one and the same `request_id`, equal to the `X-Request-ID` header |
| Request ids under load | 40 simultaneous requests | Every `task created` line carries the id of the request that got that task; no id from any other request appears |
| Service speed, no server | `pytest tests/test_service.py` | 17 tests in 0.07 s (the API tests: 35 in 0.62 s) |

---

## 9. Problems avoided

| Problem | Cause | Fix |
|---|---|---|
| Two simultaneous requests could both create the same title | Check-then-insert is two steps; another request can slip in between | The `UNIQUE` rule in the database; the repository turns its error into `DuplicateTitle`; the barrier tests and the real-server tests prove it |
| The pretend repository and SQLite disagreed | Updating an unknown id created the task in memory but did nothing in SQL | Found by the contract test on its first run; the pretend repository now ignores unknown ids |
| `/tasks/99999999999999999999/complete` would crash with a 500 | SQLite integers stop at 2^63-1; Python's do not | The route limits the id to 1 to 2^63-1, so it is a clean 422; the biggest valid id is a clean 404 |
| A crash answer would have had no request id | Starlette runs the catch-all error handler outside the middleware | The handler reads the id from the request and sets the header itself; a test checks body, header and log line |
| A blank-looking title (only zero-width characters) would have passed | They are not 'white space', so `strip()` leaves them | The title needs at least one visible character; tests cover three invisible-only inputs |
| `Straße` and `STRASSE` would be two titles | `lower()` does not fold the German ß | `casefold()`, and a test (the break-it script swaps it back to `lower()`) |
| Every log line printed twice after the app was created twice | Each `configure_logging` call added another handler | It removes the old handler first; a test and a break-it case watch this |
| A forged or giant `X-Request-ID` could pollute the logs | The id goes straight into the log line | Only 1 to 64 safe characters are kept, otherwise a new id is made |
| A typo in `.env` was silently ignored | Unknown keys have no effect, so the default is used without a word | Unknown keys in the `.env` file are an error with a spelling hint |
| A redundant database rule survived the break-it run | `CHECK (done IN (0,1))` is already implied by the done/time consistency `CHECK`, so no test can tell it apart | Removed the duplicate rule instead of writing a fake test for it |

---

## 10. What was practiced

- Starting from one function that does everything and giving each job one home
- Three layers, and a test that reads the source to keep each one in its lane
- Writing the service against a promise (`Protocol`) so a pretend repository can stand in
- A contract test that runs the same cases on two implementations, and what it found
- Putting the same rule in the service (friendly) and in the database (guaranteed)
- Making a race happen every time with a barrier, not hoping it shows up
- Mapping errors to status codes in one table, and a test that fails when the table is incomplete
- Settings from the environment and a `.env` file, with start-up checks and a clear exit code
- JSON logs, a request id carried by a `ContextVar`, and proving that ids never mix
- Breaking the app on purpose (64 ways) to prove the tests really notice

---

## 11. Known limit

Said plainly, so nobody believes more than was tested:

- **Only SQLite was used.** The `UNIQUE` rule, the `CHECK` rule and the connection-per-call approach were not run on PostgreSQL or MySQL. Their error messages and locking differ; the "UNIQUE constraint failed" text check in `sqlite.py` is SQLite-specific.
- **One process only.** The concurrency tests use threads inside one uvicorn process. Several worker processes sharing one SQLite file, or several machines, were not tested (SQLite would be the first thing to replace).
- **Windows was not tested here.** The project was built and tested on Linux with Python 3.13. The run commands for PowerShell were written from the course setup but not run on Windows; the tests that start real Python processes are the likeliest to need a change there.
- **The race demo is timing-based.** It showed duplicates in the "before" in every run here (the count changes each time), but a fast or single-core machine might show none. The deterministic proof is the barrier tests, not the demo.
- **Three break-it ideas cannot be seen by any test**, because they change nothing a user can observe: not resetting the request-id variable after a request (every request runs in its own task, so nothing can leak), `strict=True` on the schema (Pydantic already refuses a number for a text field), and the missing `ORDER BY id` (SQLite happens to return rows in id order). They are not in `break46.py`.
- **Look-alike titles are not detected** (a Cyrillic `а` in place of a Latin `a` makes a different title). Only case, spaces, accents and invisible characters are handled.
- **No authentication, no delete, no edit of a title, no pagination.** Anyone who can reach the port can use every endpoint, and `GET /tasks` returns all tasks. That is the brief, but it is not production-ready.
- **No limit on the size of a request body**; a huge title is read fully before it is refused (the 500-character setting limit applies only after).
- **One app per process.** The JSON logger is a single shared logger, so creating two apps in one process makes the second one's log settings win.
- **Python 3.10 is the lowest version intended**; older versions were not tried.
- **The "before" code is my own version** of what the course describes, not the course's exact Aspect 3 file.
- **One warning is shown by pytest**: Starlette says `starlette.testclient` with `httpx` is deprecated (it prefers `httpx2`). It does not affect any result; the pinned versions in `requirements-dev.txt` are the ones tested.
- **Uvicorn's own start-up lines are plain text**, not JSON; only the app's lines are JSON.

---

## 12. How to run it

```bash
# Windows PowerShell, from the folder that holds class-tasks-api.zip
Expand-Archive class-tasks-api.zip -DestinationPath .
cd class-tasks-api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env

python -m pytest -q          # 286 passed
python -m app                # server on http://127.0.0.1:8000  (open /docs to try every endpoint)

# in a second PowerShell window, try it:
curl.exe -s -X POST http://127.0.0.1:8000/tasks -H "Content-Type: application/json" -d "{\"title\": \"Math homework\"}"
curl.exe -s http://127.0.0.1:8000/tasks
curl.exe -s -X POST http://127.0.0.1:8000/tasks/1/complete
curl.exe -s -X POST http://127.0.0.1:8000/tasks/1/reopen
```

The server window prints one JSON line per event, and every line of one request shares one `request_id` (also sent back in the `X-Request-ID` header).

To see a bad start, open `.env`, change `APP_MAX_TITLE_LENGTH=100` to `APP_MAX_TITLE_LENGTH=abc` and run `python -m app` again: it prints what is wrong and stops. Put `100` back afterwards.

Optional extras: `python break46.py` (about 2 minutes, breaks 64 rules and expects the tests to catch each) and `python scripts/race_demo.py`.
