# Runbook: Backup Restore Drill

## Goal

Prove that backups are usable, not just present.

## Minimum Drill

1. Select the latest known good backup or snapshot.
2. Restore to an isolated target.
3. Run schema validation and a small application smoke test.
4. Record restore duration, data gap, and follow-up issues.

## Evidence To Save

- snapshot or backup identifier
- restore target
- validation commands
- duration and outcome
- issues found during restore

