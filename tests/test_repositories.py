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
