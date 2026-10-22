# Code runner

Isolated execution service behind the code sandbox (`POST /api/v1/code/execute`).
The backend never runs student code itself. It forwards the code to this container,
which the production deploy starts like this (see `scripts/ci/deploy_code_runner.sh`):

| Control | Setting |
|---|---|
| Network | `smart-tutor-sandbox`, an `--internal` Docker network: only the backend can reach it, and it has no internet |
| Secrets | none: no env file, no AWS credentials, no volumes |
| Filesystem | `--read-only` root, 64 MB `tmpfs` at `/tmp` for per-run work dirs |
| Privileges | uid 10001, `--cap-drop ALL`, `no-new-privileges` |
| Resources | 768 MB RAM (no swap), 1 CPU, 256 PIDs |
| Per run | 10 s wall clock, 8 s CPU, 1 MB file writes, 64 open files, 64 KB output, 256 MB address space for Python; at most 2 concurrent runs |

Languages: Python 3.11, JavaScript (Node), Java 17.

Local test:

```bash
docker build -t smart-tutor-code-runner sandbox/code-runner
docker run --rm -p 8080:8080 --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --cap-drop ALL --security-opt no-new-privileges --memory 768m --cpus 1 --pids-limit 256 smart-tutor-code-runner
curl -s localhost:8080/run -d '{"language":"python","code":"print(2**10)"}'
```
