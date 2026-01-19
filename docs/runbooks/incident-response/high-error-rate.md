# Runbook: High Error Rate Alert

## Metadata
- **Severity:** P1 (Critical)
- **SLA:** Response within 15 minutes
- **MTTR Target:** < 30 minutes
- **On-call:** DevOps Team
- **Last Updated:** 2026-01-07

---

## Alert Triggers

This runbook is triggered when:
- Prometheus alert: `BackendHighErrorRate` (> 5% 5xx errors for 5 minutes)
- Grafana dashboard shows red health status
- User reports of widespread errors
- AWS CloudWatch alarms for ECS task failures

---

## Symptoms

- [ ] High percentage of 5xx HTTP responses
- [ ] Increased API latency (P95 > 2s)
- [ ] Users unable to access key features (chat, research, quiz)
- [ ] Backend pods restarting frequently
- [ ] Database connection errors in logs
- [ ] AWS Bedrock API throttling errors

---

## Initial Assessment (5 minutes)

### 1. Check Current Status

```bash
# Check Grafana dashboard
open "https://grafana.your-domain.com/d/backend-api/backend-api-dashboard"

# Check pod health
kubectl get pods -n production -l app=backend

# Check recent deployments
kubectl rollout history deployment/backend -n production

# Check error rate
kubectl logs -n production -l app=backend --tail=100 | grep ERROR

# Check Prometheus
curl -s "http://prometheus:9090/api/v1/query?query=rate(http_requests_total{code=~\"5..\"}[5m])"
```

### 2. Identify Scope

Determine if the issue affects:
- [ ] All users or specific users
- [ ] All endpoints or specific endpoints
- [ ] All regions or specific availability zones
- [ ] All backend pods or specific pods

```bash
# Check error distribution by endpoint
kubectl logs -n production -l app=backend --tail=1000 | grep "ERROR" | awk '{print $5}' | sort | uniq -c | sort -rn

# Check error distribution by pod
kubectl get pods -n production -l app=backend -o wide
```

---

## Investigation Steps (10 minutes)

### Step 1: Recent Changes
```bash
# Check recent deployments (last 24 hours)
kubectl rollout history deployment/backend -n production

# Check recent Git commits
git log --since="24 hours ago" --oneline

# Check ArgoCD sync history
argocd app history backend-production
```

**If deployment within last hour:** Likely cause is recent code change.
**Action:** Proceed to Rollback (Step 5)

---

### Step 2: Database Health
```bash
# Check PostgreSQL connections
kubectl exec -n production $(kubectl get pod -n production -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U smart_tutor_user -d smart_tutor -c "SELECT count(*) FROM pg_stat_activity;"

# Check for long-running queries
kubectl exec -n production $(kubectl get pod -n production -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U smart_tutor_user -d smart_tutor -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"

# Check database locks
kubectl exec -n production $(kubectl get pod -n production -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U smart_tutor_user -d smart_tutor -c "SELECT * FROM pg_locks WHERE NOT granted;"
```

**If connection pool exhausted or deadlocks:**
**Action:** See Database Issues Runbook

---

### Step 3: External Dependencies
```bash
# Check AWS Bedrock status
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-00000001

# Test Bedrock connectivity
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --body '{"prompt":"test","max_tokens":10}' \
  /tmp/bedrock-test.json

# Check Redis connectivity
kubectl exec -n production $(kubectl get pod -n production -l app=redis -o jsonpath='{.items[0].metadata.name}') -- \
  redis-cli ping

# Check DynamoDB status (if using)
aws dynamodb describe-table --table-name smart-tutor-prod-chat-sessions
```

**If external API failures:**
**Action:** Enable circuit breaker or switch to fallback mode

---

### Step 4: Resource Constraints
```bash
# Check CPU/Memory usage
kubectl top pods -n production -l app=backend

# Check HPA status
kubectl get hpa -n production

# Check node resources
kubectl top nodes

# Check for OOMKilled pods
kubectl get pods -n production -l app=backend -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}' | grep OOMKilled
```

**If resource throttling:**
**Action:** Scale up pods (Step 6)

---

### Step 5: Application Logs
```bash
# Stream recent logs
kubectl logs -n production -l app=backend --tail=500 --timestamps

# Search for specific errors
kubectl logs -n production -l app=backend --tail=5000 | grep -A 5 -B 5 "Traceback"

# Check for rate limit errors
kubectl logs -n production -l app=backend --tail=5000 | grep "Rate limit exceeded"

# Export logs for analysis
kubectl logs -n production -l app=backend --since=1h > /tmp/backend-logs-$(date +%s).log
```

---

## Resolution Actions

### Action 1: Rollback Deployment

**When to use:** Recent deployment (< 1 hour) and no other obvious cause

```bash
# Get previous revision
PREVIOUS_REVISION=$(kubectl rollout history deployment/backend -n production | tail -2 | head -1 | awk '{print $1}')

# Rollback to previous version
kubectl rollout undo deployment/backend -n production --to-revision=$PREVIOUS_REVISION

# Monitor rollback progress
kubectl rollout status deployment/backend -n production

# Verify error rate decreased
watch -n 5 'kubectl logs -n production -l app=backend --tail=100 | grep ERROR | wc -l'
```

**Expected time:** 2-5 minutes
**Success criteria:** Error rate < 1% within 5 minutes

---

### Action 2: Scale Up Pods

**When to use:** High CPU/memory usage or increased traffic

```bash
# Scale up immediately
kubectl scale deployment/backend -n production --replicas=20

# Monitor scaling
kubectl get pods -n production -l app=backend -w

# Check if HPA needs adjustment
kubectl patch hpa backend-hpa -n production -p '{"spec":{"maxReplicas":30}}'
```

**Expected time:** 1-2 minutes
**Success criteria:** CPU usage < 70%, memory < 80%

---

### Action 3: Restart Unhealthy Pods

**When to use:** Specific pods showing issues, not systematic

```bash
# Identify unhealthy pods
UNHEALTHY_PODS=$(kubectl get pods -n production -l app=backend -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==false)]}{.metadata.name}{"\n"}{end}')

# Delete unhealthy pods (will be recreated)
for pod in $UNHEALTHY_PODS; do
  kubectl delete pod -n production $pod
done

# Monitor new pods
kubectl get pods -n production -l app=backend -w
```

**Expected time:** 1-2 minutes per pod
**Success criteria:** All pods in Running state with 1/1 ready

---

### Action 4: Enable Circuit Breaker

**When to use:** External API failures (Bedrock, SerpAPI)

```bash
# Update ConfigMap to enable circuit breaker
kubectl patch configmap backend-config -n production -p '{"data":{"CIRCUIT_BREAKER_ENABLED":"true","CIRCUIT_BREAKER_THRESHOLD":"5","CIRCUIT_BREAKER_TIMEOUT":"60"}}'

# Restart pods to pick up new config
kubectl rollout restart deployment/backend -n production
```

**Expected time:** 2-3 minutes
**Success criteria:** Errors from external APIs no longer cascading

---

### Action 5: Database Connection Pool Adjustment

**When to use:** Database connection pool exhaustion

```bash
# Increase connection pool size
kubectl set env deployment/backend -n production \
  POSTGRES_MIN_CONNECTIONS=5 \
  POSTGRES_MAX_CONNECTIONS=20

# Monitor connection usage
kubectl exec -n production $(kubectl get pod -n production -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U smart_tutor_user -d smart_tutor -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

**Expected time:** 2-3 minutes
**Success criteria:** Connection errors eliminated

---

### Action 6: Traffic Rerouting (Last Resort)

**When to use:** All other actions failed, need to protect production

```bash
# Route traffic to maintenance page
kubectl patch ingress backend-ingress -n production -p '{"spec":{"rules":[{"host":"api.your-domain.com","http":{"paths":[{"path":"/","pathType":"Prefix","backend":{"service":{"name":"maintenance-page","port":{"number":80}}}}]}}]}}'

# Notify users via status page
# Update https://status.your-domain.com with incident details
```

**Expected time:** < 1 minute
**Impact:** User-facing outage, but prevents data corruption

---

## Verification Steps

After applying any resolution:

```bash
# 1. Check error rate (should be < 1%)
kubectl logs -n production -l app=backend --tail=1000 --since=5m | grep ERROR | wc -l

# 2. Check Prometheus metrics
curl -s "http://prometheus:9090/api/v1/query?query=rate(http_requests_total{code=~\"5..\",job=\"backend\"}[5m])/rate(http_requests_total{job=\"backend\"}[5m])"

# 3. Check pod health
kubectl get pods -n production -l app=backend

# 4. Verify API endpoints
curl -f https://api.your-domain.com/health

# 5. Check user-facing functionality
# Test chat, research, quiz features manually or via automated tests

# 6. Monitor for 10 minutes
watch -n 10 'kubectl logs -n production -l app=backend --tail=100 | grep ERROR | wc -l'
```

**Success Criteria:**
- [ ] Error rate < 1% for 10 consecutive minutes
- [ ] All pods healthy (Running, 1/1 ready)
- [ ] API latency P95 < 500ms
- [ ] No user reports of errors
- [ ] Prometheus alert resolved

---

## Communication

### Initial Notification (T+0)
**To:** #incidents Slack channel, on-call engineer

```
🚨 INCIDENT: High error rate detected in production backend
Severity: P1
Current error rate: X%
Investigating: [Your Name]
Status page: https://status.your-domain.com
```

### Updates (Every 15 minutes)
```
📊 UPDATE: High error rate incident
Time: T+15
Actions taken: [List actions]
Current status: [Improving/Degraded]
Next steps: [Plan]
ETA to resolution: [Estimate]
```

### Resolution Notification
```
✅ RESOLVED: High error rate incident
Duration: X minutes
Root cause: [Brief description]
Impact: X% of requests failed
Actions taken: [Summary]
Postmortem: Will be scheduled within 48h
```

---

## Escalation

**15 minutes:** No improvement → Page senior engineer
**30 minutes:** Still critical → Engage platform team lead
**45 minutes:** Widespread outage → Notify CTO
**60 minutes:** Consider full rollback to previous stable version

**Escalation Contacts:**
- On-call Engineer: PagerDuty rotation
- Senior Engineer: [name] - [phone]
- Platform Lead: [name] - [phone]
- CTO: [name] - [phone]

---

## Post-Incident Actions

1. **Within 1 hour:**
   - [ ] Update incident tracker with timeline
   - [ ] Collect all relevant logs and metrics
   - [ ] Document root cause (preliminary)

2. **Within 24 hours:**
   - [ ] Create detailed incident report
   - [ ] Identify affected users and impact
   - [ ] Plan customer communication (if needed)

3. **Within 48 hours:**
   - [ ] Schedule postmortem meeting
   - [ ] Invite all stakeholders
   - [ ] Create action items for prevention

4. **Within 1 week:**
   - [ ] Conduct blameless postmortem
   - [ ] Document lessons learned
   - [ ] Update runbook with new insights
   - [ ] Implement preventive measures

---

## Prevention Measures

### Short-term (This week)
- [ ] Add more granular error monitoring
- [ ] Increase alerting sensitivity
- [ ] Add automated rollback triggers
- [ ] Improve health check coverage

### Medium-term (This month)
- [ ] Implement chaos engineering tests
- [ ] Add synthetic monitoring
- [ ] Improve observability (tracing)
- [ ] Add automated capacity planning

### Long-term (This quarter)
- [ ] Implement progressive delivery (canary)
- [ ] Add A/B testing framework
- [ ] Improve error budget tracking
- [ ] Add predictive alerting (ML-based)

---

## Related Runbooks
- [Database Connection Issues](./database-down.md)
- [High Latency](./high-latency.md)
- [Disk Space Full](./disk-space.md)
- [Rollback Procedure](../deployment/rollback-procedure.md)

---

## Appendix

### Common Error Patterns

**Error:** `psycopg2.OperationalError: FATAL: remaining connection slots reserved`
**Cause:** Database connection pool exhausted
**Fix:** Increase max_connections or add connection pooling (PgBouncer)

**Error:** `botocore.exceptions.ClientError: ThrottlingException`
**Cause:** AWS Bedrock API rate limit exceeded
**Fix:** Implement exponential backoff, request quota increase

**Error:** `redis.exceptions.ConnectionError: Error connecting to Redis`
**Cause:** Redis unavailable or network issue
**Fix:** Check Redis health, check network policies

**Error:** `HTTPError: 500 Internal Server Error` with no traceback
**Cause:** Worker process crash (SIGKILL/OOMKilled)
**Fix:** Increase memory limits, investigate memory leaks

---

## Change Log

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-07 | DevOps Team | Initial creation |
| | | |
