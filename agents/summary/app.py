"""Start Discharge Summary Generator A2A service (:8104 streaming).

Run from repo root:
    uv run python -m agents.summary
"""

from __future__ import annotations

import uvicorn

from agents.summary.a2a import build_a2a_app
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("summary")


def main() -> None:
    svc = get_service("summary")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8104))

    app = build_a2a_app()
    logger.info(
        "Discharge Summary Generator A2A starting on http://%s:%s (streaming)",
        host,
        port,
    )
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
