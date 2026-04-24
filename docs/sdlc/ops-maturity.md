# Ops Maturity

## Service Objectives

- Availability SLO: 99.9% monthly for customer-facing application paths.
- API readiness SLO: 99.95% monthly for `/ready`.
- Change failure rate target: less than 15% of production deploys.
- Time to mitigate Sev1 incidents: less than 30 minutes.

## Required Operational Assets

- Dashboards for latency, error rate, saturation, auth failures, and deploy health.
- Alert routing for production incidents.
- Runbooks for deploy failure, migration failure, high error rate, and restore drills.
- Incident review notes for Sev1 and Sev2 events.

## Review Cadence

- Weekly: alerts and noisy monitors
- Monthly: SLO review
- Quarterly: dependency, backup, and runbook drills

