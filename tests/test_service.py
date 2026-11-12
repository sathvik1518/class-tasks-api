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
