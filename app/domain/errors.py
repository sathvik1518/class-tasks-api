"""The ways a task request can be refused. Plain Python: no HTTP, no SQL.
Each error has a stable `code` (for programs) and a `message` (for people). The HTTP status for each lives in ONE place: app/api/errors.py."""


class TaskError(Exception):
    code = "task_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidTitle(TaskError):
    code = "invalid_title"


class DuplicateTitle(TaskError):
    code = "duplicate_title"


class TaskNotFound(TaskError):
    code = "task_not_found"
