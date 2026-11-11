"""Secret handling helpers.

No secrets are stored in files. Values are read from the environment
only, and any value that looks like a credential is redacted before
it is logged or displayed.
"""

from __future__ import annotations

import os
import re

REDACTED = "***REDACTED***"

# ``token=...`` / ``password: ...`` style assignments (case-insensitive).
_KEY_VALUE_RE = re.compile(
    r"(?i)(token|secret|password|access_token|api_key|apikey|auth)"
    r"(\s*[:=]\s*)(['\"]?)[^\s'\",}]+"
)
# ``Bearer <token>`` headers.
_BEARER_RE = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-~+/=]{8,}")
# Long hex strings (e.g. API keys / hashes) -- 20+ hex chars.
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{20,}\b")
# Long token-like strings: 32+ alphanumerics / _ / - (common token shape).
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")

_SENSITIVE_KEYS = ("token", "secret", "password", "key")


def redact(text: str) -> str:
    """Redact credential-like values from *text*.

    Replaces the value in ``token=...`` / ``password: ...`` assignments,
    ``Bearer ...`` headers, and long hex / token-like strings with
    ``***REDACTED***``. Non-string input is returned unchanged.
    """
    if not isinstance(text, str):
        return text

    def _kv_replace(match: re.Match) -> str:
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    result = _KEY_VALUE_RE.sub(_kv_replace, text)
    result = _BEARER_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", result)
    result = _LONG_HEX_RE.sub(REDACTED, result)
    result = _LONG_TOKEN_RE.sub(REDACTED, result)
    return result


def redact_dict(d: dict) -> dict:
    """Return a copy of *d* with sensitive keys / values redacted.

    Keys containing ``token`` / ``secret`` / ``password`` / ``key``
    (case-insensitive) have their value replaced wholesale. String
    values under other keys are passed through :func:`redact`;
    nested dicts are redacted recursively and lists element-wise.
    """
    if not isinstance(d, dict):
        return d
    out = {}
    for k, v in d.items():
        key_lower = str(k).lower()
        if any(s in key_lower for s in _SENSITIVE_KEYS):
            out[k] = REDACTED
        elif isinstance(v, dict):
            out[k] = redact_dict(v)
        elif isinstance(v, list):
            out[k] = [
                redact_dict(item) if isinstance(item, dict)
                else redact(item) if isinstance(item, str)
                else item
                for item in v
            ]
        elif isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


def get_secret(name: str, required: bool = False) -> str | None:
    """Return the environment variable *name*, or ``None`` if missing/empty.

    Raises :class:`ValueError` when *required* is True and the value
    is missing or empty. Never logs or prints the value.
    """
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise ValueError(f"Required secret {name!r} is not set")
        return None
    return value


def check_secrets_present(names: list[str]) -> dict[str, bool]:
    """Return ``{name: True/False}`` for whether each env var is set/non-empty.

    Only presence is reported -- never the values.
    """
    return {name: bool(os.environ.get(name)) for name in names}
