# Deployment Safety

## Required Controls

- All deployments use immutable image tags.
- Staging deploys happen from `develop` after CI succeeds.
- Production deploys happen from `main` after CI succeeds.
- Candidate health must pass before traffic or environment promotion is considered successful.
- Rollback remains a first-class workflow, not an emergency-only script.

## Release Checklist

- Confirm linked issue and PR verification.
- Confirm migration impact.
- Confirm smoke and health endpoints.
- Confirm dashboards and alerts to watch.
- Confirm rollback workflow and last known good version.

## Mandatory Follow-Up

- Review post-deploy smoke results.
- Review error rate, latency, and auth failures.
- Create a follow-up issue for any non-blocking warning left in the deploy.

