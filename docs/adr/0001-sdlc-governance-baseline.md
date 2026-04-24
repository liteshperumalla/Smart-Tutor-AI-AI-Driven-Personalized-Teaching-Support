# ADR 0001: SDLC Governance Baseline

- Status: Accepted
- Date: 2026-04-24
- Owners: Platform Engineering

## Context

The repository already had meaningful CI/CD, security scanning, and deployment automation, but the process controls around requirements, testing depth, rollout safety, operations, and environment discipline were incomplete or spread across implementation docs.

## Decision

This repository adopts the following baseline controls:

- changes start from a GitHub issue or change request
- production-impacting decisions use ADRs
- PRs must include verification and rollback notes
- CI validates application tests, security checks, migration safety, and environment discipline
- operational expectations live in runbooks and SDLC docs in-repo

## Consequences

This adds process overhead to every change, but it reduces silent risk and makes reviews more deterministic. The repository becomes easier to audit and safer to deploy.

## Rollout

The baseline is enforced through repository templates, documentation, local developer tooling, and CI workflow gates.

## Rollback

The governance assets can be relaxed by removing the templates and CI jobs, but operationally that would be a regression and should itself require a change request.

