"""Layer test: each layer may import only what it is allowed to. Reads the real source files (no running needed).
Breaks on purpose when, say, the service imports fastapi or the api imports sqlite3."""
import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
STDLIB = set(sys.stdlib_module_names)

# layer -> (third-party packages allowed, app modules allowed, standard-library modules NOT allowed)
RULES = {
    "domain": (set(), {"app.domain"}, {"sqlite3", "http", "socket", "urllib", "asyncio", "threading"}),
    "services": (set(), {"app.domain", "app.services"}, {"sqlite3", "http", "socket", "urllib"}),
    "repositories": (set(), {"app.domain", "app.repositories"}, {"http", "socket", "urllib"}),
    "api": ({"fastapi", "starlette", "pydantic"}, {"app.domain", "app.services", "app.api", "app.request_context"}, {"sqlite3"}),
    "support": (set(), {"app.request_context", "app.settings"}, {"sqlite3"}),  # settings, logging_setup, request_context
}
MAIN_FILES = {"main.py", "__main__.py"}  # the wiring: allowed to know everything


def imported_modules(source: str) -> list[tuple[str, int]]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.level if hasattr(node, "level") else 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((("." * node.level) + (node.module or ""), node.level))
    return found


def find_violations(source: str, layer: str) -> list[str]:
    third_party, app_ok, stdlib_banned = RULES[layer]
    problems = []
    for name, level in imported_modules(source):
        if level >= 1:
            problems.append(f"relative import {name!r}: use absolute imports so layers can be checked")
            continue
        top = name.split(".")[0]
        if top == "app":
            if not any(name == ok or name.startswith(ok + ".") for ok in app_ok):
                problems.append(f"{layer} must not import {name}")
        elif top in STDLIB:
            if top in stdlib_banned:
                problems.append(f"{layer} must not import {name}")
        elif top not in third_party:
            problems.append(f"{layer} must not import {name}")
    return problems


def layer_of(path: Path) -> str | None:
    rel = path.relative_to(APP)
    if rel.name in MAIN_FILES:
        return None
    return rel.parts[0] if len(rel.parts) > 1 else "support"


def source_files():
    return [p for p in sorted(APP.rglob("*.py")) if layer_of(p)]


def test_the_scan_really_sees_all_the_layers():
    layers = {layer_of(p) for p in source_files()}
    assert layers == {"domain", "services", "repositories", "api", "support"}
    assert len(source_files()) >= 18


@pytest.mark.parametrize("path", source_files(), ids=lambda p: str(p.relative_to(APP)))
def test_each_file_imports_only_what_its_layer_allows(path):
    assert find_violations(path.read_text(), layer_of(path)) == []


def test_main_files_are_the_only_ones_exempt():
    assert {p.name for p in APP.rglob("*.py") if layer_of(p) is None} == MAIN_FILES


# ---------- the checker itself: does it notice a bad import? ----------

@pytest.mark.parametrize("source,layer", [
    ("import fastapi", "services"),
    ("from fastapi import HTTPException", "services"),
    ("from starlette.requests import Request", "services"),
    ("from pydantic import BaseModel", "domain"),
    ("import sqlite3", "services"),
    ("import sqlite3", "domain"),
    ("import sqlite3", "api"),
    ("from app.repositories.sqlite import SqliteTaskRepository", "api"),
    ("from app.repositories.sqlite import SqliteTaskRepository", "services"),
    ("from app.api.routes import build_router", "services"),
    ("from app.services.tasks import TaskService", "domain"),
    ("from app.services.tasks import TaskService", "repositories"),
    ("from app.api.errors import STATUS_FOR_ERROR", "repositories"),
    ("import requests", "services"),
    ("from ..domain import task", "services"),
    ("from . import x", "api"),
    ("def f():\n    import fastapi", "services"),
    ("import os\nimport fastapi.exceptions", "domain"),
    ("import sqlite3", "support"),
    ("import fastapi", "support"),
])
def test_the_checker_catches_a_forbidden_import(source, layer):
    assert find_violations(source, layer) != []


@pytest.mark.parametrize("source,layer", [
    ("from app.domain.task import Task\nimport logging\nfrom datetime import datetime", "services"),
    ("from app.domain.errors import TaskError", "domain"),
    ("import sqlite3\nfrom app.domain.task import Task", "repositories"),
    ("from fastapi import APIRouter\nfrom app.services.tasks import TaskService", "api"),
    ("import logging\nfrom app.request_context import request_id_var", "support"),
])
def test_the_checker_allows_what_the_layer_may_use(source, layer):
    assert find_violations(source, layer) == []
