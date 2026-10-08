"""Structured logging + the scoring decision audit trail (Phase 3.4).

Two streams, both JSON (one object per line):

- **app log** → stdout (`docker compose logs`), for operations;
- **decision log** → `logs/decisions.jsonl` (size-rotated), one record per
  `/api/score` decision, so any decision can be traced to the exact model
  version and inputs.

The decision record never stores raw applicant fields — only a SHA-256 hash of
the normalized inputs. Re-hashing the same application reproduces the hash, so
a decision can be matched to its inputs without the log holding them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from creditcast.config import REPO_ROOT

LOG_DIR = Path(os.environ.get("CC_LOG_DIR", REPO_ROOT / "logs"))


class JsonFormatter(logging.Formatter):
    """Render a log record as one JSON object; dict messages are merged in."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
        }
        if isinstance(record.msg, dict):
            entry.update(record.msg)
        else:
            entry["msg"] = record.getMessage()
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging() -> logging.Logger:
    """Configure JSON logging once; returns the decision-audit logger."""
    app_log = logging.getLogger("creditcast")
    if not getattr(app_log, "_cc_configured", False):
        app_log.setLevel(logging.INFO)
        out = logging.StreamHandler()
        out.setFormatter(JsonFormatter())
        app_log.addHandler(out)
        app_log.propagate = False
        app_log._cc_configured = True

    decisions = logging.getLogger("creditcast.decisions")
    if not getattr(decisions, "_cc_configured", False):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            LOG_DIR / "decisions.jsonl", maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
        )
        fh.setFormatter(JsonFormatter())
        decisions.addHandler(fh)
        decisions._cc_configured = True  # also propagates to stdout
    return decisions


def input_hash(applicant: dict) -> str:
    """SHA-256 of the normalized application (sorted keys, no whitespace)."""
    canonical = json.dumps(applicant, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decision_record(
    *, request_id: str, model_version: dict, applicant: dict, result: dict, latency_ms: float
) -> dict:
    """The audit entry for one scoring decision (no raw applicant fields)."""
    return {
        "event": "score_decision",
        "request_id": request_id,
        "model_version": model_version,
        "input_hash": input_hash(applicant),
        "pd": result.get("pd"),
        "decision": result.get("decision"),
        "risk_band": result.get("risk_band"),
        "threshold": result.get("threshold"),
        "reason_features": [r["feature"] for r in result.get("reason_codes", [])],
        "latency_ms": round(latency_ms, 1),
    }
