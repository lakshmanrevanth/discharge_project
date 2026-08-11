"""Simple project logger.

Logs to console and to data/reports/pipeline.log (rules.yaml §6.5).
PII/PHI is redacted before each log record is emitted (SSoT §8).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from shared.guardrails.pii_redactor import redact_text
from shared.settings import get_path

_configured = False


class _PiiFilter(logging.Filter):
    """Mask phone / Aadhaar / PAN (and similar) in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            redacted = redact_text(msg)
            if redacted != msg:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


def _configure_root_handlers() -> None:
    """Attach console + file handlers once to the shared project logger."""
    global _configured
    if _configured:
        return

    root = logging.getLogger("cap_proj")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.propagate = False
    root.addFilter(_PiiFilter())

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(_PiiFilter())
    root.addHandler(console)

    log_file = get_path("pipeline_log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(_PiiFilter())
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str = "cap_proj") -> logging.Logger:
    """Return a named logger under the shared cap_proj handlers."""
    _configure_root_handlers()
    if name == "cap_proj":
        return logging.getLogger("cap_proj")
    logger = logging.getLogger(f"cap_proj.{name}")
    logger.setLevel(logging.INFO)
    return logger
