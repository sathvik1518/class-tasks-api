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
