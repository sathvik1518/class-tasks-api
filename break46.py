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
