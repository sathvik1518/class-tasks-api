# Class Tasks API

A small FastAPI API for class tasks (create, list, complete, reopen; titles are unique), built in three layers: **domain** (rules), **services** (use cases), **repositories** (SQLite), plus an **api** layer for HTTP. Errors are mapped to status codes in one table, settings come from the environment and a `.env` file (a bad value stops the app at start-up), and every log line is JSON with the request id of the request that caused it. The unique-title rule lives in the service **and** in the database, so two requests at the same moment can never make two rows.

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # Mac/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m app                        # http://127.0.0.1:8000  (docs at /docs)
```

## Test

```powershell
python -m pytest -q                  # 286 tests
python break46.py                    # 64 deliberate mistakes, all caught
python scripts/race_demo.py          # the "before" makes duplicates, the new app does not
```

| Endpoint | What it does |
|---|---|
| `POST /tasks` | create (`{"title": "..."}`), 201; 409 if the title exists; 422 if it is not valid |
| `GET /tasks?done=true\|false` | list, oldest first |
| `POST /tasks/{id}/complete` | mark done (safe to repeat) |
| `POST /tasks/{id}/reopen` | mark not done (safe to repeat) |
| `GET /health` | `{"status": "ok"}` |

Settings (see `.env.example`): `APP_DATABASE_URL`, `APP_MAX_TITLE_LENGTH`, `APP_LOG_LEVEL`, `APP_PORT`.

See `DOCUMENTATION.md` for the full write-up.
