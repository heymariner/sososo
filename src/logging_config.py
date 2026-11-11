"""Structured JSON logging for HeyMariner."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.utils.secrets import redact, redact_dict

_LOGGER_NAME = "heymariner"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Return the ``heymariner`` logger, configured once.

    Adds a plain stream handler (one JSON line per event is emitted
    by :func:`log_event` via ``logger.info``) if none is present yet,
    so repeated calls do not duplicate output.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    numeric = getattr(logging, str(level).upper(), logging.INFO)
    logger.setLevel(numeric)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(numeric)
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    """Emit one JSON log line for *event* with *fields*.

    Any field whose key contains ``token`` / ``secret`` / ``password``
    (case-insensitive) is replaced with ``***REDACTED***``; string
    values are also passed through :func:`src.utils.secrets.redact`
    so embedded ``token=...`` / ``Bearer ...`` values are hidden.
    The record carries an ISO-8601 UTC ``timestamp`` and the event name.
    """
    record: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    redacted = redact_dict(dict(fields))
    for key, value in redacted.items():
        if isinstance(value, str):
            record[key] = redact(value)
        else:
            record[key] = value
    logger.info(json.dumps(record, default=str))
