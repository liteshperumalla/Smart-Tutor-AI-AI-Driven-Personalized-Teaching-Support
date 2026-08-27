# Incident Severity Matrix & Response Playbook

> **Smart AI Tutor — Production Operations**
> Maintained by: Platform Engineering & SRE

---

## Severity Definitions

| Severity | Name | Impact | Response Time | Escalation |
|---|---|---|---|---|
| **P0** | Critical — Site Down | Complete service outage; all users affected; data at risk | **Immediate (< 5 min)** | All hands; exec notification |
| **P1** | High — Core Feature Down | Core feature broken (chat/auth/RAG down); majority of users impacted | **< 15 min** | On-call + team lead |
| **P2** | Medium — Degraded Performance | Elevated latency, partial failures, single tenant impacted | **< 1 hr** | On-call engineer |
| **P3** | Low — Minor Issue | Non-critical feature broken, cosmetic bug, alert noise | **< 4 hr (next business day)** | Ticket created |

---

## P0 — Critical Incident

### Triggers (auto-PagerDuty alert)
- `BackendServiceDown` alert fires (Prometheus)
- `FrontendDown` alert fires
- `DatabaseDown` alert fires
- SLO error budget **exhausted** (`BackendErrorBudgetExhausted`)
- Alertmanager: `severity=critical` alert lasting > 2 minutes

### Response Steps

```
1. ACKNOWLEDGE the PagerDuty alert within 5 minutes.
2. JOIN #incidents Slack channel — post: "P0 declared: [brief description]"
3. ASSIGN IC (Incident Commander) and Scribe.
4. DIAGNOSE using:
   - Grafana: https://grafana.smart-ai-tutor.com
   - Logs:     https://grafana.smart-ai-tutor.com/explore (Loki)
   - Traces:   https://jaeger.smart-ai-tutor.com
5. EXECUTE rollback if deploy is the cause:
   gh workflow run rollback-production.yml -f backend_image_tag=<last-good-tag> -f reason="P0 auto-rollback"
   OR:
   ./scripts/blue-green-deploy.sh --rollback
6. NOTIFY users via status page (https://status.smart-ai-tutor.com).
7. RESOLVE the alert when service is restored.
8. CONDUCT blameless post-mortem within 48 hours.
```

### Escalation Path
```
On-Call Engineer → Team Lead → Engineering Manager → CTO
```

---

## P1 — High Severity Incident

### Triggers
- `CriticalAPIErrorRate` > 15% for 1 minute
- `CriticalAPILatency` P95 > 5s for 2 minutes
- `CriticalDatabaseConnections` > 95%
- `BackendAvailabilityBurnRateFast` fires

### Response Steps

```
1. ACKNOWLEDGE within 15 minutes.
2. JOIN #incidents Slack.
3. TRIAGE: Determine affected endpoints / users.
4. MITIGATE: Feature flag kill-switch first, then rollback if needed:
   FEATURE_FLAG_ENHANCED_RAG=false   → disables RAG enhancements
   FEATURE_FLAG_NEW_CHAT_UI=false    → reverts chat UI to stable version
5. COMMUNICATE: Update #general or status page if user-facing.
6. RESOLVE and document in #incidents.
7. Create follow-up Jira ticket for permanent fix.
```

---

## P2 — Medium Severity Incident

### Triggers
- `HighAPIErrorRate` > 5% for 3 minutes
- `HighAPILatency` P95 > 2s for 5 minutes
- `LowCacheHitRate` < 70% for 10 minutes
- `HighRAGQueryLatency` P95 > 3s for 5 minutes
- `BackendAvailabilityBurnRateSlow` fires

### Response Steps

```
1. Acknowledge within 1 hour.
2. Investigate in next available sprint slot if non-customer-impacting.
3. Apply mitigation if available (scaling, cache warm-up, flag toggle).
4. Document findings in the incident ticket.
```

---

## P3 — Low Severity

### Triggers
- Alert noise / false positive
- Minor UI bug
- Non-core feature degraded
- `HighRAGCost` > $10/hr (not urgent but needs monitoring)

### Response Steps

```
1. Create Jira ticket.
2. Assign to next sprint.
3. No on-call page required.
```

---

## On-Call Rotation

| Role | Schedule | Primary Slack | PagerDuty Escalation Policy |
|---|---|---|---|
| **On-Call Engineer** | Weekly rotation | `@oncall-eng` | `smart-ai-tutor-primary` |
| **Team Lead Escalation** | 24/7 backup | `@team-lead` | `smart-ai-tutor-escalation` |
| **SRE Escalation** | Business hours | `@sre-team` | `smart-ai-tutor-sre` |

> **To update rotation:** Edit in PagerDuty → `smart-ai-tutor-oncall` schedule.

---

## Incident Communication Templates

### Initial Declaration (post in #incidents)
```
🚨 P[0/1] INCIDENT DECLARED
Time: [UTC timestamp]
Impact: [what is broken / who is affected]
IC: @[name]
Scribe: @[name]
Bridge: [Zoom/Slack huddle link]
Status page: https://status.smart-ai-tutor.com
```

### Status Update (every 15 min for P0, 30 min for P1)
```
⏱️ INCIDENT UPDATE — [UTC timestamp]
Status: [Investigating / Mitigating / Monitoring]
Current impact: [brief]
Next update in: [15 min]
```

### Resolution Notice
```
✅ INCIDENT RESOLVED — [UTC timestamp]
Duration: [X hours Y minutes]
Root cause: [brief]
Mitigation: [what was done]
Post-mortem: [link or ETA]
```

---

## Key Runbook Links

| Runbook | Link |
|---|---|
| High Error Rate | [high-error-rate.md](./high-error-rate.md) |
| DB Migration Failure | [../db-migration-failure.md](../db-migration-failure.md) |
| Deploy Failure | [../deploy-failure.md](../deploy-failure.md) |
| Backup Restore Drill | [../backup-restore-drill.md](../backup-restore-drill.md) |
| Blue-Green Rollback | `./scripts/blue-green-deploy.sh --rollback` |
| GitHub Rollback Workflow | `.github/workflows/rollback-production.yml` |

---

## Quick Reference: One-Liners

```bash
# Instant traffic rollback
./scripts/blue-green-deploy.sh --rollback

# GitHub Actions rollback (specify last-good tag)
gh workflow run rollback-production.yml \
  -f backend_image_tag=sha-abc1234 \
  -f reason="P0 incident rollback"

# Kill enhanced RAG pipeline via feature flag (no redeploy)
# Toggle in PostHog dashboard: enhanced_rag → OFF

# Check current production health
curl -s https://api.smart-ai-tutor.com/health | jq .

# Check SLO burn rate (Prometheus query)
# sum(rate(http_requests_total{job="backend",code=~"5.."}[1h]))
# / sum(rate(http_requests_total{job="backend"}[1h]))
```
