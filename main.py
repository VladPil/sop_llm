"""SOP LLM Executor - Entry Point.

Запускает FastAPI приложение через uvicorn.
"""

import uvicorn
from config.settings import settings


def main() -> None:
    """Запустить SOP LLM Executor."""
    uvicorn.run(
        "src.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,  # Auto-reload только в debug
        log_level=settings.log_level.lower(),
        access_log=settings.debug,  # Access log только в debug
        workers=1,  # ВАЖНО: Single worker для GPU Guard
    )


if __name__ == "__main__":
    main()
