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
