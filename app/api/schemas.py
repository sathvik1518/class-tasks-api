"""The shapes that cross the wire."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    # `title: str` only checks "is it text". What a GOOD title is (length, blank, duplicates) is a rule, so it lives in the domain.
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str


class TaskOut(BaseModel):
    id: int
    title: str
    done: bool
    created_at: datetime
    completed_at: datetime | None
