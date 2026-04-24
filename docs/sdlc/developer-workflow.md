# Developer Workflow

## Local Standards

- Use `pre-commit`.
- Run repo checks before pushing.
- Prefer reproducible scripts and Make targets over ad hoc shell history.
- Treat rollback and verification as part of implementation.

## Expected Commands

- `make bootstrap`
- `make backend`
- `make frontend`
- `make contract`
- `make migrate-validate`
- `make env-check`

## Review Hygiene

- Keep PRs narrow when possible.
- Update docs when behavior or operations change.
- Do not merge changes that rely on tribal knowledge for rollout or recovery.

