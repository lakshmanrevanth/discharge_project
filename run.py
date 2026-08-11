"""Project launcher — one entrypoint for local + NuvePro labs.

Examples:
    uv run python run.py                  # print plan
    uv run python run.py --lab            # HITL stack (default for NuvePro)
    uv run python run.py --all            # every service
    uv run python run.py --core           # EHR + MCP + A2A agents (no UIs)
    uv run python run.py --only mock_ehr,primary_mcp,hitl_dashboard

NuvePro:
    ./scripts/start.sh                        # EHR + MCP + Streamlit
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from shared.settings import REPO_ROOT, get_service, listen_host, load_agent_config

ROOT = REPO_ROOT
LOG_DIR = ROOT / "logs"

# Start order follows architecture dependencies.
SERVICE_SPECS: list[tuple[str, list[str], str]] = [
    ("mock_ehr", [sys.executable, "-m", "mock_ehr"], "Mock EHR :8050"),
    ("primary_mcp", [sys.executable, "-m", "mcp_servers.primary"], "Primary MCP :8200"),
    ("secondary_mcp", [sys.executable, "-m", "mcp_servers.secondary"], "Secondary MCP :8201"),
    ("monitor", [sys.executable, "-m", "agents.monitor"], "Monitor A2A :8103"),
    ("extractor", [sys.executable, "-m", "agents.extractor"], "Extractor A2A :8100"),
    ("normalizer", [sys.executable, "-m", "agents.normalizer"], "Normalizer A2A :8102"),
    ("validator", [sys.executable, "-m", "agents.validator"], "Validator A2A :8101"),
    ("summary", [sys.executable, "-m", "agents.summary"], "Summary A2A :8104 (streaming)"),
    ("rag", [sys.executable, "-m", "rag"], "RAG A2A :8105 (streaming)"),
    ("host_orchestrator", [sys.executable, "-m", "host"], "Host Gradio :8083"),
    ("hitl_dashboard", [sys.executable, "-m", "dashboard"], "HITL Streamlit :8501"),
]

UI_KEYS = {"host_orchestrator", "hitl_dashboard"}
CORE_KEYS = {
    "mock_ehr",
    "primary_mcp",
    "secondary_mcp",
    "monitor",
    "extractor",
    "normalizer",
    "validator",
    "summary",
    "rag",
}
# Streamlit HITL path used in demos — dashboard runs graphs in-process.
LAB_KEYS = ["mock_ehr", "primary_mcp", "secondary_mcp", "hitl_dashboard"]


def _port_of(key: str) -> int | None:
    try:
        return int(get_service(key).get("port"))
    except Exception:
        return None


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def print_plan(selected: list[str]) -> None:
    cfg = load_agent_config()
    bind = listen_host("127.0.0.1")
    print("Agentic Discharge Summaries — launcher")
    print(f"Repo root: {ROOT}")
    print(f"Config:    {ROOT / 'configs' / 'agent_config.yaml'}")
    print(f"Project:   {cfg.get('project_name', '')}")
    print(f"BIND_HOST: {bind}")
    print()
    print("Selected services:")
    by_key = {k: (cmd, label) for k, cmd, label in SERVICE_SPECS}
    for key in selected:
        if key not in by_key:
            print(f"  ? {key} (unknown)")
            continue
        _, label = by_key[key]
        port = _port_of(key)
        print(f"  • {key:<18} {label}" + (f"  (listen {bind}:{port})" if port else ""))
    print()


def resolve_selection(args: argparse.Namespace) -> list[str]:
    all_keys = [k for k, _, _ in SERVICE_SPECS]
    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip()]
    elif args.lab:
        keys = list(LAB_KEYS)
    elif args.core:
        keys = [k for k in all_keys if k in CORE_KEYS]
    elif args.all:
        keys = list(all_keys)
    else:
        return []

    if args.no_ui:
        keys = [k for k in keys if k not in UI_KEYS]
    return keys


def _ensure_env() -> None:
    env_path = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_path.exists() and example.exists():
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print("Created .env from .env.example — fill AWS keys before processing patients.")
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip():
        # settings already load_dotenv; re-check after import side-effect
        from dotenv import load_dotenv

        load_dotenv(env_path)
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip():
        print(
            "WARNING: AWS_ACCESS_KEY_ID missing in .env — "
            "Document Viewer browse works; Process patient / RAG need Bedrock."
        )


def start_services(selected: list[str]) -> list[tuple[str, subprocess.Popen]]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    by_key = {k: (cmd, label) for k, cmd, label in SERVICE_SPECS}
    procs: list[tuple[str, subprocess.Popen]] = []
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    for key in selected:
        cmd, label = by_key[key]
        log_path = LOG_DIR / f"{key}.log"
        log_f = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
        print(f"Starting {label}  →  logs/{key}.log")
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=log_f,
            stderr=subprocess.STDOUT,
            env=env,
        )
        procs.append((key, proc))
        time.sleep(0.6)
    return procs


def wait_ready(selected: list[str], timeout: float = 45.0) -> None:
    """Wait until service ports accept connections (best-effort)."""
    deadline = time.time() + timeout
    pending = {k: _port_of(k) for k in selected}
    pending = {k: p for k, p in pending.items() if p}
    print("Waiting for ports…")
    while pending and time.time() < deadline:
        for key, port in list(pending.items()):
            if _port_open(port):
                print(f"  ✓ {key} :{port}")
                pending.pop(key)
        if pending:
            time.sleep(0.5)
    for key, port in pending.items():
        print(f"  ! {key} :{port} not ready yet — check logs/{key}.log")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start discharge-summary services")
    parser.add_argument(
        "--lab",
        action="store_true",
        help="NuvePro / demo stack: Mock EHR + dual MCP + Streamlit HITL",
    )
    parser.add_argument("--all", action="store_true", help="Start every service")
    parser.add_argument("--core", action="store_true", help="EHR + MCP + A2A agents (no UIs)")
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated service keys from agent_config.yaml",
    )
    parser.add_argument("--no-ui", action="store_true", help="Skip Gradio Host + Streamlit HITL")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan only (default when no start flags)",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for ports after start",
    )
    args = parser.parse_args(argv)

    selected = resolve_selection(args)
    if not selected:
        print_plan([k for k, _, _ in SERVICE_SPECS])
        print("Dry-run only. Pass --lab (NuvePro), --all, --core, or --only KEY,KEY.")
        print("Or run:  ./scripts/start.sh")
        return 0

    _ensure_env()
    print_plan(selected)
    if args.dry_run and not (args.lab or args.all or args.core or args.only):
        return 0

    procs = start_services(selected)
    if not args.no_wait:
        wait_ready(selected)

    bind = listen_host("127.0.0.1")
    print()
    print(f"Started {len(procs)} process(es). Ctrl+C to stop all.")
    print(f"  HITL Streamlit:  http://127.0.0.1:8501  (bind {bind})")
    print(f"  Mock EHR:        http://127.0.0.1:8050")
    print(f"  Primary MCP:     http://127.0.0.1:8200/clinicaltools")
    print(f"  Secondary MCP:   http://127.0.0.1:8201/analyticstools")
    if "host_orchestrator" in selected:
        print(f"  Host Gradio:     http://127.0.0.1:8083")
    print(f"  Logs:            {LOG_DIR}/")
    print()

    def _shutdown(signum=None, frame=None):  # noqa: ARG001
        print("\nStopping services…")
        for _key, p in procs:
            if p.poll() is None:
                p.terminate()
        for _key, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            for key, p in procs:
                code = p.poll()
                if code is not None:
                    print(f"! {key} exited with code {code} — see logs/{key}.log")
                    log_path = LOG_DIR / f"{key}.log"
                    if log_path.exists():
                        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
                        if tail.strip():
                            print(tail)
                    _shutdown()
            time.sleep(1.0)
    except KeyboardInterrupt:
        _shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
