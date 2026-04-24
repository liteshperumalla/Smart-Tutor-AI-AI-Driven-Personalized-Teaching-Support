# Contributing

## Required Flow

1. Start with a GitHub issue or change request.
2. Document architectural or operational decisions in `docs/adr/` when the change affects contracts, data, rollout, or infrastructure.
3. Keep changes reviewable. Large work should land behind flags or in staged slices.
4. Every PR must include verification and rollback notes.

## Definition Of Done

- Requirements and acceptance criteria are linked in the PR.
- Tests were added or updated at the right layer.
- Security, migration, and environment impact were evaluated.
- Rollout and rollback are clear.
- Docs and runbooks were updated if production behavior changed.

## Local Workflow

- Install hooks: `make bootstrap`
- Backend checks: `make backend`
- Frontend checks: `make frontend`
- Contract checks: `make contract`
- Migration validation: `make migrate-validate`
- Environment drift check: `make env-check`

## Review Expectations

- CODEOWNERS review is expected for touched areas.
- Schema, auth, secrets, and deployment changes require explicit reviewer attention.
- PRs without linked issues, verification, or rollback notes should not merge.

