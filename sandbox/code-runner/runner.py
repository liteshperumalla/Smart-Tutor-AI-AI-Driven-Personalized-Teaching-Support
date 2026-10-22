"""Isolated code runner for the Smart Tutor AI code sandbox.

Runs untrusted student code (Python, JavaScript, Java) and returns its output.
This file is the *only* thing inside the code-runner container, which the
deploy starts with no secrets, no internet access (internal Docker network),
a read-only root filesystem, an unprivileged user and CPU/memory/PID caps.
This process adds per-run limits on top of that:

  * a fresh temp directory and a minimal environment for every run
  * CPU-time, file-size, open-file and core-dump rlimits
  * an address-space limit for Python (JVM/V8 are capped by their own flags)
  * a process-count limit (fork bombs) and a wall-clock timeout that
    kills the whole process group
  * output capped while streaming (the run is killed once it overflows),
    and a small cap on concurrent runs

API (stdlib only, no third-party dependencies):
  GET  /healthz  -> {"status": "ok"}
  POST /run      {"language": "python|javascript|java", "code": "...", "stdin": ""}
              -> {"stdout", "stderr", "exit_code", "timed_out", "duration_ms", "truncated"}
"""

from __future__ import annotations

import json
import os
import re
import resource
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("RUNNER_PORT", "8080"))
MAX_CODE_BYTES = int(os.getenv("RUNNER_MAX_CODE_BYTES", str(64 * 1024)))
MAX_OUTPUT_BYTES = int(os.getenv("RUNNER_MAX_OUTPUT_BYTES", str(64 * 1024)))
WALL_TIMEOUT_S = float(os.getenv("RUNNER_WALL_TIMEOUT_S", "10"))
CPU_LIMIT_S = int(os.getenv("RUNNER_CPU_LIMIT_S", "8"))
PY_MEMORY_BYTES = int(os.getenv("RUNNER_PY_MEMORY_MB", "256")) * 1024 * 1024
MAX_CONCURRENT = int(os.getenv("RUNNER_MAX_CONCURRENT", "2"))
MAX_PROCS = int(os.getenv("RUNNER_MAX_PROCS", "128"))
WORK_ROOT = os.getenv("RUNNER_WORK_ROOT", tempfile.gettempdir())

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_JAVA_PUBLIC_CLASS = re.compile(r"public\s+(?:final\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")


def _limits(memory_bytes: int | None):
    """Return a preexec_fn applying rlimits in the child before exec."""

    def apply() -> None:
        os.setsid()  # own process group, so a timeout can kill every child
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_S, CPU_LIMIT_S))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Per-uid process/thread cap: stops fork bombs (JVMs need ~30 threads each).
        resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCS, MAX_PROCS))
        if memory_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    return apply


def _drain(stream, sink: bytearray, overflow: threading.Event) -> None:
    """Read a pipe into `sink`, keeping at most MAX_OUTPUT_BYTES + 1 bytes."""
    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        room = MAX_OUTPUT_BYTES + 1 - len(sink)
        if room > 0:
            sink.extend(chunk[:room])
        if len(sink) > MAX_OUTPUT_BYTES:
            overflow.set()  # keep draining so the child never blocks, but stop storing


def _run(cmd: list[str], cwd: str, stdin: str, memory_bytes: int | None, timeout: float) -> dict:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": cwd, "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        preexec_fn=_limits(memory_bytes), close_fds=True,
    )
    out, err, overflow = bytearray(), bytearray(), threading.Event()
    readers = [threading.Thread(target=_drain, args=(proc.stdout, out, overflow), daemon=True),
               threading.Thread(target=_drain, args=(proc.stderr, err, overflow), daemon=True)]
    for reader in readers:
        reader.start()
    try:
        proc.stdin.write(stdin.encode("utf-8"))
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass

    timed_out = False
    deadline = started + timeout
    while proc.poll() is None:
        if overflow.is_set() or time.monotonic() >= deadline:
            timed_out = not overflow.is_set()
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # the whole group, incl. forked children
            except ProcessLookupError:
                pass
            break
        time.sleep(0.02)
    proc.wait()
    for reader in readers:
        reader.join(timeout=2)
    truncated = overflow.is_set()
    return {
        "stdout": bytes(out[:MAX_OUTPUT_BYTES]).decode("utf-8", "replace"),
        "stderr": bytes(err[:MAX_OUTPUT_BYTES]).decode("utf-8", "replace"),
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "truncated": truncated,
    }


def run_code(language: str, code: str, stdin: str = "") -> dict:
    workdir = tempfile.mkdtemp(prefix="run-", dir=WORK_ROOT)
    try:
        if language == "python":
            path = os.path.join(workdir, "main.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            return _run(["python3", "-I", "-B", path], workdir, stdin, PY_MEMORY_BYTES, WALL_TIMEOUT_S)

        if language == "javascript":
            path = os.path.join(workdir, "main.js")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            return _run(["node", "--max-old-space-size=128", path], workdir, stdin, None, WALL_TIMEOUT_S)

        if language == "java":
            match = _JAVA_PUBLIC_CLASS.search(code)
            if match:
                class_name = match.group(1)
            else:
                class_name = "Main"
                code = f"public class Main {{\n  public static void main(String[] args) throws Exception {{\n{code}\n  }}\n}}\n"
            path = os.path.join(workdir, f"{class_name}.java")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            jvm = ["-Xmx192m", "-Xss1m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-Xshare:auto"]
            started = time.monotonic()
            compiled = _run(["javac", "-J-Xmx256m", "-d", workdir, path], workdir, "", None, WALL_TIMEOUT_S)
            if compiled["exit_code"] != 0 or compiled["timed_out"]:
                compiled["stage"] = "compile"
                return compiled
            remaining = max(1.0, WALL_TIMEOUT_S - (time.monotonic() - started))
            result = _run(["java", *jvm, "-cp", workdir, class_name], workdir, stdin, None, remaining)
            result["duration_ms"] += compiled["duration_ms"]
            return result

        return {"stdout": "", "stderr": f"Unsupported language: {language}", "exit_code": 2,
                "timed_out": False, "duration_ms": 0, "truncated": False}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "code-runner/1"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/healthz":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/run":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_CODE_BYTES * 2:
            self._send(413, {"error": "request too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            language = str(payload.get("language", "python"))
            code = str(payload["code"])
            stdin = str(payload.get("stdin", ""))[:MAX_CODE_BYTES]
        except (ValueError, KeyError, TypeError):
            self._send(400, {"error": "expected JSON with 'language' and 'code'"})
            return
        if len(code.encode("utf-8")) > MAX_CODE_BYTES:
            self._send(413, {"error": f"code exceeds {MAX_CODE_BYTES // 1024} KB"})
            return
        if not _slots.acquire(blocking=False):
            self._send(429, {"error": "runner busy, try again in a few seconds"})
            return
        try:
            self._send(200, run_code(language, code, stdin))
        except Exception as exc:  # report, never crash the server
            self._send(500, {"error": f"runner error: {type(exc).__name__}"})
        finally:
            _slots.release()

    def log_message(self, fmt: str, *args) -> None:
        # One line per request, without request bodies (student code stays private).
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"code-runner listening on :{PORT} (max {MAX_CONCURRENT} concurrent runs)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
