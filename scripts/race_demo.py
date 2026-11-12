"""Shows the 'before' app making duplicate rows when many requests with the same title arrive together,
then the new app refusing them. Timing-based: how many duplicates you see changes from run to run (that is the point of a race).
Run from the project folder:   python scripts/race_demo.py"""
import os
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

REQUESTS, ROUNDS = 40, 5


def serve(app):
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}"


def blast(base, title):
    barrier = threading.Barrier(REQUESTS, timeout=20)

    def go(_):
        barrier.wait()
        return httpx.post(f"{base}/tasks", json={"title": title}, timeout=60).status_code

    with ThreadPoolExecutor(max_workers=REQUESTS) as pool:
        return list(pool.map(go, range(REQUESTS)))


def main():
    tmp = Path(tempfile.mkdtemp())
    os.environ["APP_DATABASE_URL"] = f"sqlite:///{tmp / 'before.db'}"
    from before.before_app import app as before_app
    for name, app, db in (("before", before_app, tmp / "before.db"), ("after", create_app(Settings(database_url=f"sqlite:///{tmp / 'after.db'}", log_level="ERROR")), tmp / "after.db")):
        server, base = serve(app)
        rows = []
        for round_no in range(ROUNDS):
            codes = blast(base, f"Same title {round_no}")
            with sqlite3.connect(db) as conn:
                rows.append(conn.execute("SELECT COUNT(*) FROM tasks WHERE title = ?", (f"Same title {round_no}",)).fetchone()[0])
        server.should_exit = True
        print(f"{name}: rows made per round (should be 1 each): {rows}")


main()
