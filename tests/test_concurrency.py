"""Two requests at the same time must never make two rows. Run against a REAL server."""
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx


def post_together(base_url, titles):
    barrier = threading.Barrier(len(titles), timeout=10)

    def go(title):
        barrier.wait()  # release every request at the same instant
        return httpx.post(f"{base_url}/tasks", json={"title": title}, timeout=30)

    with ThreadPoolExecutor(max_workers=len(titles)) as pool:
        return list(pool.map(go, titles))


def test_two_requests_with_the_same_title_make_one_row(live_server):
    answers = post_together(live_server.base_url, ["Same title"] * 2)
    assert sorted(a.status_code for a in answers) == [201, 409]
    assert len(httpx.get(f"{live_server.base_url}/tasks").json()) == 1


def test_thirty_requests_with_the_same_title_make_one_row(live_server):
    answers = post_together(live_server.base_url, ["Same title"] * 30)
    codes = sorted(a.status_code for a in answers)
    assert codes == [201] + [409] * 29
    assert len(httpx.get(f"{live_server.base_url}/tasks").json()) == 1


def test_same_title_in_different_spelling_at_the_same_time_makes_one_row(live_server):
    answers = post_together(live_server.base_url, ["Quiz", "QUIZ", " quiz ", "Quiz  "] * 5)
    assert sorted(a.status_code for a in answers) == [201] + [409] * 19
    assert len(httpx.get(f"{live_server.base_url}/tasks").json()) == 1


def test_different_titles_at_the_same_time_all_succeed_with_distinct_ids(live_server):
    answers = post_together(live_server.base_url, [f"task {i}" for i in range(30)])
    assert all(a.status_code == 201 for a in answers)
    assert sorted(a.json()["id"] for a in answers) == list(range(1, 31))


def test_completing_the_same_task_at_the_same_time_is_harmless(live_server):
    task = httpx.post(f"{live_server.base_url}/tasks", json={"title": "a"}).json()
    barrier = threading.Barrier(10, timeout=10)

    def go(_):
        barrier.wait()
        return httpx.post(f"{live_server.base_url}/tasks/{task['id']}/complete", timeout=30)

    with ThreadPoolExecutor(max_workers=10) as pool:
        answers = list(pool.map(go, range(10)))
    assert all(a.status_code == 200 for a in answers)
    assert len({a.json()["completed_at"] for a in answers}) <= 10  # all succeeded; the stored task is done
    final = httpx.get(f"{live_server.base_url}/tasks?done=true").json()
    assert len(final) == 1 and final[0]["done"] and final[0]["completed_at"]
