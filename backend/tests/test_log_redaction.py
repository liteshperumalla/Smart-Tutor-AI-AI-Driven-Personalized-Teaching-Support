"""Usernames and email addresses must not reach logs or analytics."""

import io
import json
import logging

from backend.log_redaction import RedactionFilter, install, redact_text, user_ref


def test_user_ref_is_stable_and_opaque():
    ref = user_ref("alice")
    assert ref == user_ref("alice ")
    assert ref.startswith("u_") and "alice" not in ref
    assert user_ref("bob") != ref


def test_user_ref_keeps_case_distinct_usernames_apart():
    # Usernames are case-sensitive in the account stores; emails are not.
    assert user_ref("Alice") != user_ref("alice")
    assert user_ref("Alice@Example.com") == user_ref("alice@example.com")


def test_user_ref_is_idempotent_only_for_generated_refs():
    ref = user_ref("alice")
    assert user_ref(ref) == ref
    assert user_ref(None) == "anonymous"
    # A username that merely looks like a pseudonym is still hashed.
    assert user_ref(str(ref)) != ref
    assert user_ref("anonymous") != "anonymous"


def test_deleted_by_is_pseudonymized():
    log, stream = _capture("redaction-deleted-by")
    log.info("account deleted", extra={"extra_data": {"details": {"deleted_by": "admin1"}}})
    assert "admin1" not in stream.getvalue()


def test_exception_tracebacks_are_redacted():
    log, stream = _capture("redaction-traceback")
    try:
        raise ValueError("cannot open /data/alice@example.com/profile.json")
    except ValueError:
        log.exception("load failed")
    out = stream.getvalue()
    assert "ValueError" in out
    assert "alice@example.com" not in out


def test_json_formatter_emits_the_redacted_traceback():
    from backend.logger import JsonFormatter

    stream = io.StringIO()
    handler = install(logging.StreamHandler(stream))
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("redaction-json")
    log.addHandler(handler)
    log.propagate = False
    try:
        raise ValueError("bad user bob@example.com")
    except ValueError:
        log.exception("failed")
    record = json.loads(stream.getvalue())
    assert "bob@example.com" not in record["exception"]
    assert "ValueError" in record["exception"]


def test_redact_text_masks_every_email():
    text = redact_text("from alice@example.com cc bob.smith+x@uni.edu ok")
    assert "@" not in text
    assert user_ref("alice@example.com") in text


def _capture(logger_name: str):
    stream = io.StringIO()
    handler = install(logging.StreamHandler(stream))
    handler.setFormatter(logging.Formatter("%(message)s|%(extra_data)s", defaults={"extra_data": ""}))
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
