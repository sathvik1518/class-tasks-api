"""HTTP only: read the request, call the service, shape the answer. No rules, no SQL, no status-code choices for errors."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.api.deps import get_service
from app.api.schemas import TaskCreate, TaskOut
from app.services.tasks import TaskService

MAX_ID = 2**63 - 1  # the biggest number SQLite can hold; anything bigger would crash the database call

TaskId = Path(ge=1, le=MAX_ID)


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.post("/tasks", status_code=201, response_model=TaskOut)
    def create_task(body: TaskCreate, service: TaskService = Depends(get_service)):
        return service.create(body.title)

    @router.get("/tasks", response_model=list[TaskOut])
    def list_tasks(done: bool | None = None, service: TaskService = Depends(get_service)):
        return service.list_tasks(done)

    @router.post("/tasks/{task_id}/complete", response_model=TaskOut)
    def complete_task(task_id: int = TaskId, service: TaskService = Depends(get_service)):
        return service.complete(task_id)

    @router.post("/tasks/{task_id}/reopen", response_model=TaskOut)
    def reopen_task(task_id: int = TaskId, service: TaskService = Depends(get_service)):
        return service.reopen(task_id)

    return router
