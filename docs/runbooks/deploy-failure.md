# Runbook: Deploy Failure

## Trigger

- staging or production deploy workflow fails
- post-deploy smoke test fails
- healthy candidate never becomes ready

## Immediate Actions

1. Stop further deploy attempts.
2. Identify the failing version, workflow run, and environment.
3. Check deploy logs, candidate container logs, `/ready`, and `/health`.
4. If user impact exists, start rollback immediately.

## Validation

- Confirm image tag and git SHA.
- Confirm secrets and environment file path.
- Confirm migration status.
- Confirm readiness and metrics endpoints.

## Recovery

- Use the repository rollback workflow for the environment.
- Re-run smoke checks after rollback.
- Open or update a change request with findings.

