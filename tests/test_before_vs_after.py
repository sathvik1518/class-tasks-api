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
