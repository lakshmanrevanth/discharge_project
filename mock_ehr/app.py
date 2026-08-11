"""FastAPI Mock EHR entrypoint (:8050).

Run from repo root:
    uv run uvicorn mock_ehr.app:app --host 127.0.0.1 --port 8050

Or:
    uv run python -m mock_ehr.app
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from mock_ehr.routes import router
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("mock_ehr")

app = FastAPI(
    title="Mock EHR System",
    description="FA5 Mock EHR — patients, meds, allergies, labs, care plans",
    version="0.1.0",
)
app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    svc = get_service("mock_ehr")
    logger.info(
        "Mock EHR starting on %s:%s",
        svc.get("host", "127.0.0.1"),
        svc.get("port", 8050),
    )


def main() -> None:
    """Start uvicorn using host/port from configs/agent_config.yaml."""
    svc = get_service("mock_ehr")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8050))
    uvicorn.run("mock_ehr.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
