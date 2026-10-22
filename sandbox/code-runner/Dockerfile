# Isolated runner for the code sandbox. Holds no app code or secrets; the deploy
# runs it read-only, unprivileged, without internet, and with resource caps.
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs default-jdk-headless \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 runner \
    && useradd --system --uid 10001 --gid runner --no-create-home --shell /usr/sbin/nologin runner

COPY runner.py /srv/runner.py

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1
CMD ["python3", "-u", "/srv/runner.py"]
