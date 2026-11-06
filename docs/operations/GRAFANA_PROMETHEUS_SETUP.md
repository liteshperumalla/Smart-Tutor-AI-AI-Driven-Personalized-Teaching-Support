# Connecting Grafana and Prometheus to Smart AI Tutor

This guide provides step-by-step instructions to connect your **Grafana** and **Prometheus** accounts or infrastructure to the Smart AI Tutor platform.

---

## 🏛️ Monitoring Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Smart AI Tutor Services                         │
│                                                                        │
│  FastAPI Backend (port 8000)        Next.js Frontend (port 4000)       │
│  Metrics at: /metrics               Metrics at: /api/metrics           │
└──────────────────┬─────────────────────────────┬───────────────────────┘
                   │                             │
                   ▼ (Scrape every 30-60s)       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       Prometheus Scrape Engine                         │
│  • Local: monitoring/prometheus/prometheus.yml                         │
│  • EC2 / Prod: monitoring/prometheus/prometheus-ec2.yml                │
│  • Evaluates rules in monitoring/prometheus/alerts.yml                 │
└──────────────────┬─────────────────────────────┬───────────────────────┘
                   │                             │
    Option A: Push │              Option B: Pull │
   (remote_write)  │              (Grafana DS)   │
                   ▼                             ▼
┌───────────────────────────────────┐ ┌──────────────────────────────────┐
│      Grafana Cloud Account        │ │   Local / Self-Hosted Grafana    │
│  • Hosted Prometheus TSDB         │ │   • Local at: localhost:3001     │
│  • Remote Write Endpoint          │ │   • Pre-provisioned Dashboards   │
│  • Cloud Dashboards & Alerts      │ │   • Pre-wired DataSource         │
└───────────────────────────────────┘ └──────────────────────────────────┘
```

---

## Option 1: Grafana Cloud (production, free tier)

Production Prometheus on EC2 ([`prometheus-ec2.yml`](../../monitoring/prometheus/prometheus-ec2.yml)) pushes metrics to Grafana Cloud with `remote_write`. The stack is on the **free tier**, which allows:

| Limit | Free tier |
|---|---|
| Metrics | 10,000 active series |
| Retention | 14 days |
| Users | 3 active users (also 3 Grafana IRM users) |

Grafana Cloud counts metrics usage as **max(active series, data points per minute)**, so a series scraped every 15s counts as four. The config is set up to stay well under the limit:

- **Scrape intervals:** 60s for every job except the backend, which is 30s because two alerts use 2-minute rate windows. Don't lower them without checking usage.
- **Only dashboard metrics are sent:** `write_relabel_configs` keeps the metrics the dashboards in [`monitoring/grafana/dashboards/`](../../monitoring/grafana/dashboards/) query, plus `up`. cAdvisor, most node-exporter metrics, Prometheus' own metrics and Python runtime metrics stay in the local Prometheus, which alerting and the EC2 Grafana still use.
- **New dashboard metric:** add it to that allowlist. `backend/tests/test_grafana_cloud_metrics.py` fails if a dashboard queries a metric the allowlist drops.
- **Local development** ([`prometheus.yml`](../../monitoring/prometheus/prometheus.yml)) doesn't send anything to Grafana Cloud.

To check usage, open the usage and billing dashboards in the Grafana Cloud portal; the "active series" and "DPM" panels show how close the stack is to the limit.

### Credentials
- **Remote write:** the endpoint and instance ID are in `prometheus-ec2.yml`. The token (a Cloud Access Policy token with `metrics:write`) is written to `monitoring/prometheus/grafana-cloud-token` on the EC2 host by `.github/workflows/observability-production.yml`, never committed.
- **Dashboard sync:** the **Sync Dashboards To Grafana Cloud** job uploads the dashboard JSON through the Grafana API. It needs `GRAFANA_CLOUD_STACK_URL` and `GRAFANA_CLOUD_DASHBOARD_TOKEN` (a service-account token with the Editor role).

### Idle stack
A free-tier stack that nobody has used for a while is paused, and its API answers HTTP 503 while it resumes. The dashboard sync retries 429/502/503/504 for about four minutes before failing. If it still fails, open the stack in a browser to wake it, then re-run the workflow.

---

## Option 2: Connect an Existing External Grafana Instance

If you already host an existing Grafana instance (on a central server or cloud VM):

### Step 1: Expose the Prometheus Endpoint
Ensure your Prometheus instance is reachable from your external Grafana server:
- If hosted on AWS EC2, ensure the security group permits inbound TCP traffic on port `9090` (or `443` if routed through Nginx reverse proxy).
- Standard secure proxy configuration in Nginx:
  ```nginx
  location /prometheus/ {
      proxy_pass http://127.0.0.1:9090/;
      proxy_set_header Host $host;
      auth_basic "Monitoring Access";
      auth_basic_user_file /etc/nginx/.htpasswd;
  }
  ```

### Step 2: Add Prometheus Data Source in Grafana
1. In Grafana, navigate to **Connections** -> **Data Sources** -> **Add data source**.
2. Select **Prometheus**.
3. Set the **Prometheus server URL**:
   - Same network/VPC: `http://<PROMETHEUS_IP>:9090`
   - Local Docker host: `http://host.docker.internal:9090`
   - Reverse proxy: `https://<YOUR_DOMAIN>/prometheus`
4. Under **Settings**:
   - HTTP Method: `POST`
   - Scrape interval: `60s` (the production default)
5. Click **Save & Test**. You will see: *"Successfully queried the Prometheus API."*

### Step 3: Import Pre-built Dashboards
Import the dashboards located in [`monitoring/grafana/dashboards/`](../../monitoring/grafana/dashboards/).

---

## Option 3: Run the Built-in Local Observability Stack

The repository includes a production-grade, containerized Prometheus and Grafana stack pre-configured with all dashboards and data source provisioning.

### Step 1: Prepare Environment
Create `.env.observability` in the repository root (or copy from `.env.example`):
```bash
GRAFANA_ADMIN_PASSWORD=your_secure_grafana_password
GRAFANA_PORT_EXPOSE=3001
POSTGRES_HOST=postgres
POSTGRES_DB=smart_tutor
POSTGRES_USER=tutor_user
POSTGRES_PASSWORD=your_db_password
REDIS_EXPORTER_ADDRESS=redis:6379
REDIS_PASSWORD=your_redis_password
```

### Step 2: Start the Monitoring Containers
```bash
docker compose -f docker-compose.observability.yml up -d
```

### Step 3: Access Dashboards
- **Grafana**: `http://localhost:3001` (Username: `admin`, Password: `${GRAFANA_ADMIN_PASSWORD}`)
- **Prometheus**: `http://localhost:9090`
- **Alertmanager**: `http://localhost:9093`

The dashboards (`Smart AI Tutor Dashboards`) and datasource (`Prometheus`) are auto-provisioned on startup.

---

## 🔍 Validation & Health Verification

Verify that metrics are being scraped and collected:

### 1. Check Backend Metrics Endpoint
```bash
curl -s http://localhost:8000/metrics | grep http_requests_total
```
Output should contain request counts partitioned by endpoint and status code.

### 2. Check Prometheus Scrape Targets
Open `http://localhost:9090/targets` in your browser.
Ensure all targets report **UP (1/1)**:
- `backend-api` (FastAPI `/metrics`)
- `frontend` (Next.js `/api/metrics`)
- `prometheus` (Prometheus internal metrics)
- `postgresql` / `redis` (database exporters)

### 3. Verify Alerting Rules
Open `http://localhost:9090/alerts`.
Verify the following rules are loaded:
- `BackendServiceDown`
- `HighAPILatency` (REST endpoints > 2s)
- `HighLLMLatency` (Generative AI streaming > 30s)
- `CriticalErrorRate` (> 15%)
- `RedisCacheHitRateLow` (< 50%)
