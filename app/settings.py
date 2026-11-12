"""Settings come from the environment (and an optional .env file). Wrong values stop the app at start-up with a clear message,
not on the first request an hour later."""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_DATABASE_URL = "sqlite:///./class_tasks.db"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
KNOWN_KEYS = ("APP_DATABASE_URL", "APP_MAX_TITLE_LENGTH", "APP_LOG_LEVEL", "APP_PORT")


class StartupError(Exception):
    """The app cannot start. The message says why, in plain words."""


class SettingsError(StartupError):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    max_title_length: int = 100
    log_level: str = "INFO"
    port: int = 8000

    @property
    def database_path(self) -> str:
        return self.database_url[len("sqlite:///"):]

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None, env_file: str | Path | None = ".env") -> "Settings":
        """Real environment variables win over the .env file. Every problem is collected, then reported together."""
        environ = os.environ if environ is None else environ
        file_values = read_env_file(env_file) if env_file else {}
        values = {**file_values, **{k: v for k, v in environ.items() if k in KNOWN_KEYS}}
        problems: list[str] = []
        defaults = cls()

        def text(key: str, default: str) -> str | None:
            if key not in values:
                return default
            value = values[key].strip()
            if not value:
                problems.append(f"{key} is set but empty. Remove the line to use the default ({default}), or give it a value.")
                return None
            return value

        def whole_number(key: str, default: int, low: int, high: int) -> int | None:
            raw = text(key, str(default))
            if raw is None:
                return None
            if not re.fullmatch(r"[0-9]+", raw):
                problems.append(f"{key}={raw!r} is not a whole number. Use digits only, for example {default}.")
                return None
            number = int(raw)
            if not low <= number <= high:
                problems.append(f"{key}={number} is out of range. Use a number from {low} to {high}.")
                return None
            return number

        database_url = text("APP_DATABASE_URL", defaults.database_url)
        if database_url is not None:
            if not database_url.startswith("sqlite:///"):
                problems.append(f"APP_DATABASE_URL={database_url!r} is not supported. Use sqlite:///path/to/file.db (this app only knows SQLite).")
                database_url = None
            elif database_url[len("sqlite:///"):] in ("", ":memory:"):
                problems.append("APP_DATABASE_URL needs a real file path after sqlite:/// (an in-memory database would be empty on every connection).")
                database_url = None
        max_title_length = whole_number("APP_MAX_TITLE_LENGTH", defaults.max_title_length, 1, 500)
        port = whole_number("APP_PORT", defaults.port, 1, 65535)
        log_level = text("APP_LOG_LEVEL", defaults.log_level)
        if log_level is not None:
            if log_level.upper() not in LOG_LEVELS:
                problems.append(f"APP_LOG_LEVEL={log_level!r} is not a level. Use one of: {', '.join(LOG_LEVELS)}.")
                log_level = None
            else:
                log_level = log_level.upper()
        for key in file_values:  # a typo in .env would otherwise be ignored silently
            if key not in KNOWN_KEYS:
                hint = difflib.get_close_matches(key, KNOWN_KEYS, n=1)
                problems.append(f"{key} in the .env file is not a setting this app knows." + (f" Did you mean {hint[0]}?" if hint else ""))
        if problems:
            raise SettingsError("The settings are not valid:\n" + "\n".join(f"  - {p}" for p in problems))
        return cls(database_url=database_url, max_title_length=max_title_length, log_level=log_level, port=port)


_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def parse_env_text(text: str) -> dict[str, str]:
    """KEY=value lines. `#` starts a comment. Quotes around a value are removed. Bad lines are reported with their number."""
    values: dict[str, str] = {}
    first_seen: dict[str, int] = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE.match(stripped)
        if not match:
            problems.append(f"line {number}: expected KEY=value, got {stripped!r}")
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw[:1] in ("'", '"'):
            end = raw.find(raw[0], 1)
            value = raw[1:end] if end != -1 else raw[1:]
        else:
            value = re.split(r"\s#", raw, maxsplit=1)[0].strip()
        if key in first_seen:
            problems.append(f"line {number}: {key} is already set on line {first_seen[key]}")
            continue
        first_seen[key] = number
        values[key] = value
    if problems:
        raise SettingsError("The .env file is not valid:\n" + "\n".join(f"  - {p}" for p in problems))
    return values


def read_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None or not Path(path).is_file():
        return {}  # no .env file is fine: the environment and the defaults still work
    return parse_env_text(Path(path).read_text(encoding="utf-8"))
