"""Start Clinical Extractor A2A service (:8100).

Run from repo root:
    uv run python -m agents.extractor
"""

from __future__ import annotations

import uvicorn

from agents.extractor.a2a import build_a2a_app
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("extractor")


def main() -> None:
    svc = get_service("extractor")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8100))

    app = build_a2a_app()
    logger.info("Clinical Extractor A2A starting on http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
