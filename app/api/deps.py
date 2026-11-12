from fastapi import Request

from app.services.tasks import TaskService


def get_service(request: Request) -> TaskService:
    return request.app.state.service
