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
                   ▼ (Scrape every 10-15s)       ▼
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

## Option 1: Connect Your Grafana Cloud Account (Recommended)

Grafana Cloud allows you to ship all system and application metrics to a fully managed cloud backend without hosting TSDB storage.

### Step 1: Retrieve Your Grafana Cloud Remote Write Credentials
1. Log in to your [Grafana Cloud Portal](https://grafana.com/).
2. On your account launchpad, locate the **Prometheus** card and click **Send Metrics** (or **Details**).
3. Note the following three values:
   - **Remote Write Endpoint URL**: e.g., `https://prometheus-prod-XX-prod-us-central-0.grafana.net/api/prom/push`
   - **Username / Instance ID**: e.g., `123456`
   - **Password / API Token**: Create or copy an API Token with the `MetricsPublisher` (or Admin) role.

### Step 2: Configure `remote_write` in Prometheus
Open [`monitoring/prometheus/prometheus.yml`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/prometheus/prometheus.yml) (or [`monitoring/prometheus/prometheus-ec2.yml`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/prometheus/prometheus-ec2.yml) for EC2/production) and uncomment the `remote_write` block:

```yaml
remote_write:
  - url: 'https://prometheus-prod-XX-prod-us-central-0.grafana.net/api/prom/push'
    basic_auth:
      username: '123456'
      password: 'glc_YOUR_API_TOKEN_HERE'
    queue_config:
      max_samples_per_send: 1000
      max_shards: 10
      capacity: 2500
```

### Step 3: Reload or Restart Prometheus
Apply the updated configuration:
```bash
# If Prometheus is running locally via Docker:
docker compose -f docker-compose.observability.yml restart prometheus

# Or reload configuration live via HTTP POST:
curl -X POST http://localhost:9090/-/reload
```

### Step 4: Import Smart AI Tutor Dashboards into Grafana Cloud
1. In Grafana Cloud, navigate to **Dashboards** -> **New** -> **Import**.
2. Upload the JSON files from the project repository:
   - [`monitoring/grafana/dashboards/application-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/grafana/dashboards/application-dashboard.json) — API requests, latency (P50/P90/P99), error rate (4xx/5xx).
   - [`monitoring/grafana/dashboards/rag-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/grafana/dashboards/rag-dashboard.json) — LLM tokens, model response latency, RAG cache hit rate.
   - [`monitoring/grafana/dashboards/infrastructure-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/grafana/dashboards/infrastructure-dashboard.json) — CPU, RAM, Disk, and container metrics.
3. Select your Grafana Cloud Prometheus data source when prompted and click **Import**.

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
   - Scrape interval: `15s`
5. Click **Save & Test**. You will see: *"Successfully queried the Prometheus API."*

### Step 3: Import Pre-built Dashboards
Import the dashboards located in [`monitoring/grafana/dashboards/`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/grafana/dashboards/).

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
