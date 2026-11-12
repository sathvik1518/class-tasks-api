import os
import subprocess
import socket
import sys
import time
from pathlib import Path

import httpx
import pytest

from app.main import create_app
from app.settings import KNOWN_KEYS, Settings, SettingsError, StartupError, parse_env_text, read_env_file

ROOT = Path(__file__).resolve().parent.parent


def load(env=None, file_text=None, tmp=None):
    path = None
    if file_text is not None:
        path = tmp / ".env"
        path.write_text(file_text)
    return Settings.load(environ=env or {}, env_file=path)


def test_defaults_when_nothing_is_set(tmp_path):
    s = load({}, tmp=tmp_path)
    assert (s.database_url, s.max_title_length, s.log_level, s.port) == ("sqlite:///./class_tasks.db", 100, "INFO", 8000)


def test_environment_values_are_used(tmp_path):
    s = load({"APP_MAX_TITLE_LENGTH": "40", "APP_LOG_LEVEL": "debug", "APP_PORT": "9000", "APP_DATABASE_URL": "sqlite:///x/y.db"}, tmp=tmp_path)
    assert (s.max_title_length, s.log_level, s.port, s.database_path) == (40, "DEBUG", 9000, "x/y.db")


def test_values_are_trimmed(tmp_path):
    assert load({"APP_MAX_TITLE_LENGTH": "  25 "}, tmp=tmp_path).max_title_length == 25


@pytest.mark.parametrize("value", ["abc", "1.5", "-3", "+5", "1e3", "1_0", "١٢", "ten", "0x10", "5 5"])
def test_max_title_length_must_be_digits(value, tmp_path):
    with pytest.raises(SettingsError) as e:
        load({"APP_MAX_TITLE_LENGTH": value}, tmp=tmp_path)
    assert "APP_MAX_TITLE_LENGTH" in str(e.value) and "whole number" in str(e.value) and repr(value.strip()) in str(e.value)


@pytest.mark.parametrize("value", ["0", "501", "99999"])
def test_max_title_length_range(value, tmp_path):
    with pytest.raises(SettingsError, match="from 1 to 500"):
        load({"APP_MAX_TITLE_LENGTH": value}, tmp=tmp_path)


@pytest.mark.parametrize("value", ["1", "500"])
def test_max_title_length_edges_are_allowed(value, tmp_path):
    assert load({"APP_MAX_TITLE_LENGTH": value}, tmp=tmp_path).max_title_length == int(value)


@pytest.mark.parametrize("value", ["0", "65536", "abc", "-1"])
def test_port_must_be_valid(value, tmp_path):
    with pytest.raises(SettingsError, match="APP_PORT"):
        load({"APP_PORT": value}, tmp=tmp_path)


@pytest.mark.parametrize("value", ["LOUD", "10", "TRACE", "critical"])
def test_log_level_must_be_known(value, tmp_path):
    with pytest.raises(SettingsError, match="APP_LOG_LEVEL"):
        load({"APP_LOG_LEVEL": value}, tmp=tmp_path)


@pytest.mark.parametrize("value", ["postgres://u@h/db", "tasks.db", "sqlite://tasks.db", "sqlite:///", "sqlite:///:memory:", "http://x"])
def test_database_url_must_be_a_sqlite_file(value, tmp_path):
    with pytest.raises(SettingsError, match="APP_DATABASE_URL"):
        load({"APP_DATABASE_URL": value}, tmp=tmp_path)


def test_an_empty_value_is_an_error_not_a_silent_default(tmp_path):
    with pytest.raises(SettingsError, match="set but empty"):
        load({"APP_PORT": ""}, tmp=tmp_path)


def test_all_problems_are_reported_together(tmp_path):
    with pytest.raises(SettingsError) as e:
        load({"APP_MAX_TITLE_LENGTH": "abc", "APP_PORT": "0", "APP_LOG_LEVEL": "LOUD"}, tmp=tmp_path)
    text = str(e.value)
    assert "APP_MAX_TITLE_LENGTH" in text and "APP_PORT" in text and "APP_LOG_LEVEL" in text


def test_the_error_names_what_to_do(tmp_path):
    with pytest.raises(SettingsError) as e:
        load({"APP_MAX_TITLE_LENGTH": "abc"}, tmp=tmp_path)
    assert "Use digits only, for example 100" in str(e.value)


def test_unrelated_environment_variables_are_ignored(tmp_path):
    assert load({"PATH": "/bin", "APP_ID": "x", "APPDATA": "y"}, tmp=tmp_path).port == 8000


# ---------- the .env file ----------

def test_env_file_values_are_used(tmp_path):
    s = load({}, "APP_MAX_TITLE_LENGTH=30\nAPP_LOG_LEVEL=WARNING\n", tmp_path)
    assert (s.max_title_length, s.log_level) == (30, "WARNING")


def test_real_environment_beats_the_env_file(tmp_path):
    s = load({"APP_MAX_TITLE_LENGTH": "10"}, "APP_MAX_TITLE_LENGTH=30\n", tmp_path)
    assert s.max_title_length == 10


def test_a_bad_value_in_the_env_file_stops_loading(tmp_path):
    with pytest.raises(SettingsError, match="APP_MAX_TITLE_LENGTH='abc'"):
        load({}, "APP_MAX_TITLE_LENGTH=abc\n", tmp_path)


def test_a_missing_env_file_is_fine(tmp_path):
    assert Settings.load(environ={}, env_file=tmp_path / "nope.env").port == 8000


def test_env_file_comments_quotes_and_blank_lines():
    text = '# comment\n\nAPP_PORT=9000   # trailing comment\nAPP_DATABASE_URL="sqlite:///a b/c.db"\nAPP_LOG_LEVEL=\'DEBUG\'\n  export APP_MAX_TITLE_LENGTH = 7\n'
    assert parse_env_text(text) == {"APP_PORT": "9000", "APP_DATABASE_URL": "sqlite:///a b/c.db", "APP_LOG_LEVEL": "DEBUG", "APP_MAX_TITLE_LENGTH": "7"}


def test_a_hash_inside_a_value_without_a_space_is_kept():
    assert parse_env_text("APP_DATABASE_URL=sqlite:///a#b.db")["APP_DATABASE_URL"] == "sqlite:///a#b.db"


def test_malformed_lines_are_reported_with_their_numbers():
    with pytest.raises(SettingsError) as e:
        parse_env_text("APP_PORT=1\nthis is not valid\n=oops\nOK=1\n")
    assert "line 2" in str(e.value) and "line 3" in str(e.value) and "line 4" not in str(e.value)


def test_duplicate_keys_in_the_env_file_are_an_error():
    with pytest.raises(SettingsError, match="line 3: APP_PORT is already set on line 1"):
        parse_env_text("APP_PORT=1\nOTHER=2\nAPP_PORT=3\n")


def test_a_typo_in_the_env_file_is_caught_with_a_hint(tmp_path):
    with pytest.raises(SettingsError) as e:
        load({}, "APP_MAX_TITLE_LEN=5\n", tmp_path)
    assert "APP_MAX_TITLE_LEN" in str(e.value) and "Did you mean APP_MAX_TITLE_LENGTH" in str(e.value)


def test_env_example_is_valid_and_matches_the_defaults(tmp_path):
    s = Settings.load(environ={}, env_file=ROOT / ".env.example")
    assert s == Settings()


def test_env_example_documents_every_setting_and_nothing_else():
    keys = set(read_env_file(ROOT / ".env.example"))
    assert keys == set(KNOWN_KEYS)
    assert set(Settings.__dataclass_fields__) == {"database_url", "max_title_length", "log_level", "port"}


def test_env_file_is_ignored_by_git():
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()
    assert ".env.example" not in (ROOT / ".gitignore").read_text().splitlines()


# ---------- stopping at start-up ----------

def test_create_app_refuses_bad_settings_object_via_load(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MAX_TITLE_LENGTH", "abc")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SettingsError):
        create_app()


def test_create_app_refuses_an_unopenable_database(tmp_path):
    with pytest.raises(StartupError, match="Cannot open the database"):
        create_app(Settings(database_url=f"sqlite:///{tmp_path}/no/such/dir/x.db"))


def run_app(env_extra, cwd, timeout=20):
    env = {**os.environ, "PYTHONPATH": str(ROOT), **env_extra}
    for key in KNOWN_KEYS:
        if key not in env_extra:
            env.pop(key, None)
    return subprocess.run([sys.executable, "-m", "app"], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def test_bad_setting_stops_the_real_process_before_it_listens(tmp_path):
    t0 = time.time()
    r = run_app({"APP_MAX_TITLE_LENGTH": "abc"}, tmp_path)
    assert r.returncode == 2 and time.time() - t0 < 10
    assert "Cannot start" in r.stderr and "APP_MAX_TITLE_LENGTH='abc'" in r.stderr
    assert "Traceback" not in r.stderr and "Uvicorn running" not in r.stderr + r.stdout


def test_bad_value_in_a_real_env_file_stops_the_real_process(tmp_path):
    (tmp_path / ".env").write_text("APP_PORT=nope\n")
    r = run_app({}, tmp_path)
    assert r.returncode == 2 and "APP_PORT='nope'" in r.stderr


def test_unopenable_database_stops_the_real_process(tmp_path):
    r = run_app({"APP_DATABASE_URL": f"sqlite:///{tmp_path}/missing/x.db"}, tmp_path)
    assert r.returncode == 2 and "Cannot open the database" in r.stderr


def test_good_settings_start_a_real_process_that_answers(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "APP_PORT": str(port), "APP_DATABASE_URL": f"sqlite:///{tmp_path}/p.db", "APP_LOG_LEVEL": "INFO"}
    proc = subprocess.Popen([sys.executable, "-m", "app"], cwd=tmp_path, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            pytest.fail("server never answered")
        r = httpx.post(f"http://127.0.0.1:{port}/tasks", json={"title": "from a real process"})
        assert r.status_code == 201
    finally:
        proc.terminate()
        out, err = proc.communicate(timeout=10)
    import json
    json_lines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert any(l["message"] == "task created" and l["request_id"] == r.headers["x-request-id"] for l in json_lines)
    assert '"GET /health HTTP/1.1"' not in out + err and '"POST /tasks HTTP/1.1"' not in out + err  # uvicorn's own access log is off
