# Environment Discipline

## Principles

- Build once, promote by immutable version where possible.
- Environment-specific values live in secrets or environment configuration, not source code.
- Example env files define the contract, not the live secret values.
- Drift between env contracts must be visible and reviewed.

## Required Practices

- Keep `.env.example` current with required keys and placeholders.
- Validate environment contract drift in CI.
- Never commit live credentials.
- Document production-only configuration and safety switches.

