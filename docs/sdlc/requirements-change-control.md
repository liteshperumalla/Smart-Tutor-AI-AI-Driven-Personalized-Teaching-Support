# Requirements And Change Control

## Policy

- Every material change starts from an issue.
- High-risk changes use the `Change Request` template.
- Architectural, data, deployment, and security decisions require an ADR.
- PRs must link the issue or change request and include verification plus rollback.

## Required Before Merge

- Problem statement and acceptance criteria exist.
- Risk and blast radius are stated.
- Rollback path is documented.
- Data and secret impact are reviewed.

## Required Before Production Release

- CI is green.
- Migration safety is validated if schemas changed.
- Smoke verification and observability checks are defined.
- Any manual approval happens through the protected environment gate.

