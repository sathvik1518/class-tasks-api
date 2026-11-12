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
