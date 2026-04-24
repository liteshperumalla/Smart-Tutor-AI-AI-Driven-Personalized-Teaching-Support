# Stronger Testing Pyramid

## Target Distribution

- Unit tests cover pure logic and edge cases.
- Integration tests cover FastAPI routes, auth, storage, and middleware behavior.
- Contract tests protect the Next.js proxy and backend interface assumptions.
- End-to-end tests cover primary user journeys.

## Repository Rules

- New logic should land with unit or route-level tests first.
- Proxy or API compatibility changes require contract coverage.
- Schema or storage changes require migration validation.
- Production-critical paths should have smoke checks and at least one rollback-safe verification path.

## CI Gates

- Backend tests
- Frontend tests
- Contract tests
- Migration validation
- Security checks

