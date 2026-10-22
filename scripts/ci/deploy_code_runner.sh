#!/usr/bin/env bash
# Build (if changed) and (re)start the isolated code-runner container on the
# production host, and attach it to an internal-only Docker network that only
# the backend joins. Runs ON the EC2 host; the deploy copies sandbox/code-runner
# to $RUNNER_SRC first.
#
#   RUNNER_SRC      directory holding Dockerfile + runner.py (default ~/code-runner-src)
#   RUNNER_IMAGE    use this pre-built image instead of building (local testing)
set -euo pipefail

RUNNER_SRC="${RUNNER_SRC:-$HOME/code-runner-src}"
NETWORK="${SANDBOX_NETWORK:-smart-tutor-sandbox}"
CONTAINER="${RUNNER_CONTAINER:-smart-tutor-code-runner}"

if [ -z "${RUNNER_IMAGE:-}" ]; then
  test -f "$RUNNER_SRC/Dockerfile" && test -f "$RUNNER_SRC/runner.py"
  # Tag by content so an unchanged runner is never rebuilt (EC2 disk is tight
  # and the deploy prunes build cache).
  hash="$(cat "$RUNNER_SRC/Dockerfile" "$RUNNER_SRC/runner.py" | sha256sum | cut -c1-12)"
  RUNNER_IMAGE="smart-tutor-code-runner:${hash}"
  if docker image inspect "$RUNNER_IMAGE" >/dev/null 2>&1; then
    echo "Code runner image ${RUNNER_IMAGE} already built"
  else
    echo "=== Building ${RUNNER_IMAGE} ==="
    docker build --pull -t "$RUNNER_IMAGE" "$RUNNER_SRC"
  fi
fi

# --internal: containers on this network can reach each other but not the internet.
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  docker network create --internal "$NETWORK"
fi

current="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER" 2>/dev/null || true)"
running="$(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null || true)"
if [ "$current" = "$RUNNER_IMAGE" ] && [ "$running" = "true" ]; then
  echo "Code runner already running ${RUNNER_IMAGE}"
else
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  # No --env-file and no volumes: the runner holds no secrets and no app data.
  docker run -d \
    --name "$CONTAINER" \
    --init \
    --restart unless-stopped \
    --network "$NETWORK" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,size=64m \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --user 10001:10001 \
    --memory 768m --memory-swap 768m \
    --cpus 1 \
    --pids-limit 256 \
    --log-opt max-size=5m --log-opt max-file=2 \
    "$RUNNER_IMAGE" >/dev/null
  echo "Started ${CONTAINER} (${RUNNER_IMAGE})"
fi

for _ in $(seq 1 30); do
  if docker exec "$CONTAINER" python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" >/dev/null 2>&1; then
    echo "Code runner healthy"
    # Old content-tagged images are no longer referenced; reclaim the space.
    docker images --format '{{.Repository}}:{{.Tag}}' 'smart-tutor-code-runner' \
      | grep -vx "$RUNNER_IMAGE" | xargs -r docker rmi >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 2
done
echo "::error::Code runner did not become healthy"
docker logs --tail 50 "$CONTAINER" || true
exit 1
