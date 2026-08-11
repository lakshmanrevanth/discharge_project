"""CLI: uv run python -m dashboard  → Streamlit on http://127.0.0.1:8501"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from shared.settings import get_service, listen_host


def main() -> None:
    svc = get_service("hitl_dashboard")
    host = listen_host(svc.get("host", "127.0.0.1"))
    port = int(svc.get("port", 8501))
    app = Path(__file__).resolve().parent / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.address",
        str(host),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
