"""`python -m app` starts the server. A bad setting prints one clear message and exits with code 2, before anything listens."""
import sys

import uvicorn

from app.main import create_app
from app.settings import Settings, StartupError


def main() -> int:
    try:
        settings = Settings.load()
        app = create_app(settings)
    except StartupError as error:
        print(f"Cannot start the Class Tasks API.\n{error}", file=sys.stderr)
        return 2
    uvicorn.run(app, host="127.0.0.1", port=settings.port, access_log=False)  # our own access line carries the request id
    return 0


if __name__ == "__main__":
    sys.exit(main())
