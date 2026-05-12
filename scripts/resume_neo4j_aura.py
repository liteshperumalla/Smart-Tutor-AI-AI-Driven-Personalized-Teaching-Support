#!/usr/bin/env python3
"""Resume a paused Neo4j Aura instance.

This script is intentionally dependency-free so it can run from GitHub Actions
or a small host cron without installing the application requirements.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_API_BASE_URL = "https://api.neo4j.io/v1"
DEFAULT_TOKEN_URL = "https://api.neo4j.io/oauth/token"

RUNNING_STATES = {"running", "ready"}
PAUSED_STATES = {"paused", "stopped"}
WAIT_STATES = {"resuming", "starting", "creating", "updating", "pending"}


class AuraApiError(RuntimeError):
    """Raised when the Aura API returns an unexpected response."""


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", "replace")
        detail = raw_body[:500] if raw_body else exc.reason
        raise AuraApiError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AuraApiError(f"{method} {url} failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise AuraApiError(f"{method} {url} returned non-JSON response") from exc


def get_access_token(client_id: str, client_secret: str, token_url: str) -> str:
    credentials = f"{client_id}:{client_secret}".encode("utf-8")
    auth = base64.b64encode(credentials).decode("ascii")
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    data = _request_json(
        "POST",
        token_url,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=body,
    )
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise AuraApiError("Aura token response did not include access_token")
    return token


def _instance_payload(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else response


def _status(instance: dict[str, Any]) -> str:
    raw = instance.get("status") or instance.get("state") or "unknown"
    return str(raw).strip().lower()


def get_instance(api_base_url: str, instance_id: str, token: str) -> dict[str, Any]:
    response = _request_json(
        "GET",
        f"{api_base_url.rstrip('/')}/instances/{instance_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return _instance_payload(response)


def resume_instance(api_base_url: str, instance_id: str, token: str) -> dict[str, Any]:
    response = _request_json(
        "POST",
        f"{api_base_url.rstrip('/')}/instances/{instance_id}/resume",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        body=b"{}",
    )
    return _instance_payload(response)


def wait_until_running(
    api_base_url: str,
    instance_id: str,
    token: str,
    *,
    timeout_seconds: int,
    interval_seconds: int,
) -> tuple[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    last_instance: dict[str, Any] = {}
    last_status = "unknown"

    while time.monotonic() < deadline:
        last_instance = get_instance(api_base_url, instance_id, token)
        last_status = _status(last_instance)
        print(f"Aura instance {instance_id} status: {last_status}", flush=True)
        if last_status in RUNNING_STATES:
            return last_status, last_instance
        time.sleep(interval_seconds)

    return last_status, last_instance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume a paused Neo4j Aura instance.")
    parser.add_argument("--instance-id", default=_env("NEO4J_AURA_INSTANCE_ID"))
    parser.add_argument("--api-base-url", default=_env("NEO4J_AURA_API_BASE_URL") or DEFAULT_API_BASE_URL)
    parser.add_argument("--token-url", default=_env("NEO4J_AURA_TOKEN_URL") or DEFAULT_TOKEN_URL)
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(_env("NEO4J_AURA_POLL_TIMEOUT_SECONDS") or "420"),
        help="Seconds to wait for the instance to become running.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(_env("NEO4J_AURA_POLL_INTERVAL_SECONDS") or "15"),
        help="Seconds between status polls.",
    )
    parser.add_argument("--no-wait", action="store_true", help="Request resume but do not poll for running status.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client_id = _env("NEO4J_AURA_CLIENT_ID", "NEO4J_AURA_API_CLIENT_ID")
    client_secret = _env("NEO4J_AURA_CLIENT_SECRET", "NEO4J_AURA_API_CLIENT_SECRET")

    missing = []
    if not args.instance_id:
        missing.append("NEO4J_AURA_INSTANCE_ID")
    if not client_id:
        missing.append("NEO4J_AURA_CLIENT_ID")
    if not client_secret:
        missing.append("NEO4J_AURA_CLIENT_SECRET")
    if missing:
        print(f"Missing required configuration: {', '.join(missing)}", file=sys.stderr)
        _write_output("action", "configuration_missing")
        _write_output("status", "unknown")
        return 2

    action = "checked"
    status = "unknown"
    instance_name = ""

    try:
        token = get_access_token(client_id, client_secret, args.token_url)
        instance = get_instance(args.api_base_url, args.instance_id, token)
        status = _status(instance)
        instance_name = str(instance.get("name") or "")
        print(f"Aura instance {args.instance_id} initial status: {status}", flush=True)

        if status in RUNNING_STATES:
            action = "already_running"
            print("No resume needed.")
            return 0

        if status in PAUSED_STATES:
            action = "resume_requested"
            resumed = resume_instance(args.api_base_url, args.instance_id, token)
            status = _status(resumed)
            instance_name = str(resumed.get("name") or instance_name)
            print(f"Resume requested for {args.instance_id}; API status is now {status}.", flush=True)
        elif status in WAIT_STATES:
            action = "waited_for_running"
            print(f"Instance is already transitioning ({status}); waiting for running status.", flush=True)
        else:
            raise AuraApiError(f"Instance is in an unsupported state for auto-resume: {status}")

        if not args.no_wait:
            status, instance = wait_until_running(
                args.api_base_url,
                args.instance_id,
                token,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
            )
            instance_name = str(instance.get("name") or instance_name)

        if status not in RUNNING_STATES:
            raise AuraApiError(f"Instance did not become running before timeout; last status: {status}")

        action = "resumed" if action == "resume_requested" else action
        print(f"Aura instance {args.instance_id} is running.")
        return 0
    except Exception as exc:
        print(f"Neo4j Aura resume failed: {exc}", file=sys.stderr)
        return 1
    finally:
        _write_output("action", action)
        _write_output("status", status)
        _write_output("instance_id", args.instance_id)
        _write_output("instance_name", instance_name)


if __name__ == "__main__":
    raise SystemExit(main())
