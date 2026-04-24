# Data And Database Lifecycle

## Rules

- Schema changes must be migration-backed.
- Migrations must be safe on an empty database and on the current production schema line.
- Destructive data changes require explicit rollback notes or forward-fix strategy.
- Backups and restore drills are part of delivery, not just infrastructure setup.

## Minimum Controls

- Validate migrations in CI.
- Keep backup and restore scripts versioned.
- Run periodic restore drills and record results.
- Document retention and data ownership for each persisted store.

## Current Repository Paths

- Migration workflow: `.github/workflows/database-migrations.yml`
- Backup scripts: `scripts/dr/backup/`
- Restore scripts: `scripts/dr/restore/`
- Local database utility: `scripts/db.sh`

