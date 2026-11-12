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
