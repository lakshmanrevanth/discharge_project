"""Start Clinical RAG Q&A A2A service (:8105 streaming).

Run from repo root:
    uv run python -m rag
"""

from __future__ import annotations

import uvicorn

from rag.a2a import build_a2a_app
from shared.logger import get_logger
from shared.settings import get_service, listen_host

logger = get_logger("rag")


def main() -> None:
    svc = get_service("rag")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8105))

    app = build_a2a_app()
    logger.info(
        "Clinical RAG Q&A A2A starting on http://%s:%s (streaming)",
        host,
        port,
    )
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
