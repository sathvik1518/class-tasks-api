"""The request id of the request being served right now. A ContextVar is a variable that is separate for every request
(and follows the work into the thread pool), so two requests at the same time never see each other's id."""
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
