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
