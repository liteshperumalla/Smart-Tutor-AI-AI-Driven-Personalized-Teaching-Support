"""
Keep usernames and email addresses out of logs.

Logs are shipped to CloudWatch/Loki/Grafana, kept for weeks and read by more
people than the user database, so they must not carry direct identifiers.

- ``user_ref(value)`` turns a username or email into a stable pseudonym
  (``u_<12 hex>``): the same user always maps to the same reference, so one
  user's events can still be correlated, but the name is not recoverable
  without the key.
- ``RedactionFilter`` is attached to every log handler. It masks any email
  address in the rendered message and pseudonymizes identity fields passed
  as structured ``extra`` data (username, email, user_id, ...).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from typing import Any, Optional

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Structured fields whose values identify a person.
_IDENTITY_KEYS = {
    "username", "user", "user_id", "email", "distinct_id", "actual_username", "deleted_by",
}


class UserRef(str):
    """A pseudonym produced by user_ref().

    Marked by type rather than recognised by shape: a user may register a
    username that looks like a pseudonym, and that must still be hashed.
    """


def _key() -> bytes:
    raw = os.getenv("LOG_PSEUDONYM_KEY") or os.getenv("SECRET_KEY") or "smart-ai-tutor-logs"
    return raw.encode()


def user_ref(value: Optional[str]) -> str:
    """Stable, non-reversible reference for a username or email.

    Usernames are case-sensitive in the account stores ("Alice" and "alice"
    can be different accounts), so only emails are case-folded.
    """
    if isinstance(value, UserRef):
        return value
    if not value:
        return UserRef("anonymous")
    normalized = str(value).strip()
    if "@" in normalized:
        normalized = normalized.lower()
    digest = hmac.new(_key(), normalized.encode(), hashlib.sha256).hexdigest()
    return UserRef(f"u_{digest[:12]}")


def redact_text(text: str) -> str:
    """Replace every email address in ``text`` with its pseudonym."""
    return _EMAIL_RE.sub(lambda m: user_ref(m.group(0)), text)


def _redact_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(key, v) for v in value)
    if isinstance(value, str):
        if key in _IDENTITY_KEYS:
            return user_ref(value)
        return redact_text(value)
    return value


class RedactionFilter(logging.Filter):
    """Mask emails in messages and pseudonymize identity fields in extras."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = redact_text(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        for key in _IDENTITY_KEYS | {"extra_data"}:
            if hasattr(record, key):
                setattr(record, key, _redact_value(key, getattr(record, key)))
        # Tracebacks are formatted after filtering, so render and redact the
        # exception here; formatters use record.exc_text when it is set.
        if record.exc_info and not record.exc_text:
            try:
                record.exc_text = redact_text(_TRACEBACK_FORMATTER.formatException(record.exc_info))
            except Exception:
                pass
        elif record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True


_TRACEBACK_FORMATTER = logging.Formatter()


def install(handler: logging.Handler) -> logging.Handler:
    """Attach the redaction filter to ``handler`` (idempotent)."""
    if not any(isinstance(f, RedactionFilter) for f in handler.filters):
        handler.addFilter(RedactionFilter())
    return handler
