"""Entry point for running the server."""

import uvicorn
from .config import Settings

settings = Settings()

if __name__ == "__main__":
    uvicorn.run(
        "vizio_control.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
