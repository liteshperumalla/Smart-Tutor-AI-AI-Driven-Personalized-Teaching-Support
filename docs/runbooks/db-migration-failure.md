# Runbook: Database Migration Failure

## Trigger

- migration workflow fails
- deploy fails because schema is behind
- app starts but queries fail after release

## Immediate Actions

1. Freeze further deploys.
2. Capture failing migration revision and database target.
3. Check whether the database is partially migrated.
4. Decide between rollback and forward-fix based on blast radius.

## Validation

- Review Alembic history and current revision.
- Review application errors tied to changed tables or indexes.
- Confirm backup freshness before any destructive action.

## Recovery

- If safe, run the rollback workflow or downgrade step.
- If downgrade is not safe, prepare a forward-fix migration and restore service.
- Record the incident and update the migration notes.

