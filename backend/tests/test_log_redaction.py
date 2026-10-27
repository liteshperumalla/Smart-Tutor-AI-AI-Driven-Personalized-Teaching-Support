"""Usernames and email addresses must not reach logs or analytics."""

import io
import json
import logging

from backend.log_redaction import RedactionFilter, install, redact_text, user_ref


def test_user_ref_is_stable_and_opaque():
    ref = user_ref("Alice")
    assert ref == user_ref("alice ")
    assert ref.startswith("u_") and "alice" not in ref
    assert user_ref("bob") != ref


def test_user_ref_is_idempotent_and_keeps_anonymous():
    ref = user_ref("alice")
    assert user_ref(ref) == ref
    assert user_ref(None) == "anonymous"
    assert user_ref("anonymous") == "anonymous"


def test_redact_text_masks_every_email():
    text = redact_text("from alice@example.com cc bob.smith+x@uni.edu ok")
    assert "@" not in text
    assert user_ref("alice@example.com") in text


def _capture(logger_name: str):
    stream = io.StringIO()
    handler = install(logging.StreamHandler(stream))
    handler.setFormatter(logging.Formatter("%(message)s|%(extra_data)s"))
    log = logging.getLogger(logger_name)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log, stream


def test_filter_redacts_messages_args_and_identity_extras():
    log, stream = _capture("redaction-test")
    log.info(
        "login for %s",
        "alice@example.com",
        extra={"extra_data": {"username": "alice", "email": "alice@example.com", "ip": "1.2.3.4"}},
    )
    out = stream.getvalue()
    assert "alice" not in out
    assert "1.2.3.4" in out
    assert user_ref("alice") in out


def test_install_is_idempotent():
    handler = logging.StreamHandler(io.StringIO())
    install(handler)
    install(handler)
    assert sum(isinstance(f, RedactionFilter) for f in handler.filters) == 1


def test_security_logger_pseudonymizes_username(caplog):
    from backend.security_logger import SecurityLogger

    with caplog.at_level(logging.INFO, logger="security"):
        SecurityLogger.log_login_success(username="alice", ip_address="1.2.3.4")
    record = caplog.records[-1]
    assert "alice" not in record.getMessage()
    assert record.extra_data["username"] == user_ref("alice")
    json.dumps(record.extra_data)
