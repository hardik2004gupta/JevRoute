"""Entry point: run with `python -m jevroute.main` or `uvicorn jevroute.api.app:app`."""

import uvicorn

from jevroute.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "jevroute.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    main()
