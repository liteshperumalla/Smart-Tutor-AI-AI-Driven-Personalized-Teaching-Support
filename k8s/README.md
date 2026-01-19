# Kubernetes Deployment Manifests

Production-grade Kubernetes manifests for Smart AI Tutor platform.

## 📋 Overview

This directory contains complete Kubernetes deployment configurations for:
- **Backend API** (FastAPI) with auto-scaling
- **Frontend** (Next.js) with auto-scaling
- **PostgreSQL** (StatefulSet) with persistent storage
- **Redis** (Cache) with metrics exporter
- **Ingress** (ALB/NGINX) with SSL/TLS
- **Monitoring** (Prometheus/Grafana) - separate configs
- **Network Policies** for security

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer (ALB/NLB)                │
│                   SSL/TLS Termination (ACM)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
┌───────▼────────┐              ┌─────────▼────────┐
│   Frontend     │              │   Backend API     │
│   (Next.js)    │◄────────────►│   (FastAPI)      │
│   3 replicas   │              │   3-20 replicas   │
│   HPA enabled  │              │   HPA enabled     │
└────────────────┘              └──────────┬────────┘
                                           │
                    ┌──────────────────────┼──────────────┐
                    │                      │              │
           ┌────────▼────────┐    ┌───────▼──────┐  ┌───▼──────┐
           │   PostgreSQL    │    │    Redis     │  │   AWS    │
           │  (StatefulSet)  │    │   (Cache)    │  │ Services │
           │   100GB PVC     │    │  Sentinel    │  │ DynamoDB │
           └─────────────────┘    └──────────────┘  │ S3       │
                                                     │ Bedrock  │
                                                     └──────────┘
```

## 📁 Directory Structure

```
k8s/
├── backend/              # Backend API manifests
│   ├── deployment.yaml   # Deployment with 3 replicas
│   ├── service.yaml      # ClusterIP service
│   ├── configmap.yaml    # Environment configuration
│   ├── secret.yaml.template  # Secrets template
│   ├── hpa.yaml          # Horizontal Pod Autoscaler
│   └── pdb.yaml          # Pod Disruption Budget
│
├── frontend/             # Frontend manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── hpa.yaml
│
├── postgres/             # PostgreSQL database
│   ├── statefulset.yaml  # StatefulSet with persistent storage
│   ├── service.yaml      # Headless + ClusterIP services
│   ├── configmap.yaml    # PostgreSQL configuration
│   └── secret.yaml.template
│
├── redis/                # Redis cache
│   ├── deployment.yaml   # Deployment with exporter
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml.template
│
├── ingress/              # Traffic routing
│   ├── ingress.yaml      # ALB/NGINX ingress
│   ├── certificate.yaml  # cert-manager certificate
│   └── network-policy.yaml  # Network policies
│
├── base/                 # Base resources
│   ├── namespace.yaml
│   ├── resource-quota.yaml
│   └── kustomization.yaml
│
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites

1. **Kubernetes Cluster** (EKS, GKE, AKS, or local)
   ```bash
   # Verify cluster access
   kubectl cluster-info
   kubectl get nodes
   ```

2. **kubectl** installed (v1.24+)
   ```bash
   kubectl version --client
   ```

3. **Container Registry** (ECR, GCR, Docker Hub)
   ```bash
   # AWS ECR example
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   ```

4. **Ingress Controller** (AWS ALB Controller or NGINX)
   ```bash
   # Install AWS ALB Controller
   kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json

   # Or install NGINX Ingress
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
   ```

5. **cert-manager** (for SSL certificates with NGINX)
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
   ```

### Step 1: Build and Push Container Images

```bash
# Build backend
docker build -t <REGISTRY>/smart-ai-tutor-backend:latest -f backend/Dockerfile .
docker push <REGISTRY>/smart-ai-tutor-backend:latest

# Build frontend
docker build -t <REGISTRY>/smart-ai-tutor-frontend:latest -f frontend/Dockerfile .
docker push <REGISTRY>/smart-ai-tutor-frontend:latest
```

### Step 2: Create Secrets

```bash
# Create namespace first
kubectl create namespace smart-ai-tutor

# Backend secrets
kubectl create secret generic backend-secrets \
  --from-literal=POSTGRES_USER=smart_tutor_user \
  --from-literal=POSTGRES_PASSWORD=<STRONG_PASSWORD> \
  --from-literal=REDIS_PASSWORD=<STRONG_PASSWORD> \
  --from-literal=JWT_SECRET_KEY=<STRONG_SECRET> \
  --from-literal=GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID> \
  --from-literal=GOOGLE_CLIENT_SECRET=<GOOGLE_CLIENT_SECRET> \
  --from-literal=AWS_ACCESS_KEY_ID=<AWS_KEY> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<AWS_SECRET> \
  --namespace smart-ai-tutor

# PostgreSQL secrets
kubectl create secret generic postgres-secrets \
  --from-literal=POSTGRES_USER=smart_tutor_user \
  --from-literal=POSTGRES_PASSWORD=<STRONG_PASSWORD> \
  --namespace smart-ai-tutor

# Redis secrets
kubectl create secret generic redis-secrets \
  --from-literal=REDIS_PASSWORD=<STRONG_PASSWORD> \
  --namespace smart-ai-tutor
```

**RECOMMENDED: Use AWS Secrets Manager or Vault**

```bash
# Using External Secrets Operator with AWS Secrets Manager
kubectl apply -f https://raw.githubusercontent.com/external-secrets/external-secrets/main/deploy/crds/bundle.yaml
helm install external-secrets external-secrets/external-secrets -n external-secrets-system --create-namespace
```

### Step 3: Update Configuration

1. **Update image references** in `base/kustomization.yaml`:
   ```yaml
   images:
     - name: smart-ai-tutor-backend
       newName: <YOUR_REGISTRY>/smart-ai-tutor-backend
       newTag: v1.0.0
     - name: smart-ai-tutor-frontend
       newName: <YOUR_REGISTRY>/smart-ai-tutor-frontend
       newTag: v1.0.0
   ```

2. **Update ingress** in `ingress/ingress.yaml`:
   - Replace `REPLACE_WITH_ACM_CERTIFICATE_ARN` with your ACM certificate ARN
   - Update hostnames (`smart-ai-tutor.com`, `api.smart-ai-tutor.com`)

3. **Update ConfigMaps**:
   - `backend/configmap.yaml`: Update AWS region, S3 bucket, CORS origins
   - `frontend/configmap.yaml`: Update API URLs

### Step 4: Deploy to Kubernetes

```bash
# Deploy using kubectl
kubectl apply -k k8s/base/

# Or deploy individually
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/redis/
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/ingress/
```

### Step 5: Verify Deployment

```bash
# Check all resources
kubectl get all -n smart-ai-tutor

# Check pods
kubectl get pods -n smart-ai-tutor
kubectl logs -n smart-ai-tutor -l component=backend --tail=100

# Check services
kubectl get svc -n smart-ai-tutor

# Check ingress
kubectl get ingress -n smart-ai-tutor
kubectl describe ingress smart-ai-tutor-ingress -n smart-ai-tutor

# Check HPA
kubectl get hpa -n smart-ai-tutor

# Check PDB
kubectl get pdb -n smart-ai-tutor
```

## 📊 Monitoring

### Metrics Endpoints

- **Backend metrics**: `http://backend-api:8000/metrics`
- **Redis metrics**: `http://redis-service:9121/metrics`
- **Postgres metrics**: Deploy postgres-exporter separately

### Prometheus Scraping

Pods are annotated for Prometheus auto-discovery:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### Health Checks

All services have production-grade health checks:
- **Liveness Probe**: Restart pod if unhealthy
- **Readiness Probe**: Remove from load balancer if not ready
- **Startup Probe**: Allow slow startup (up to 150 seconds)

## 🔐 Security Features

### 1. **Pod Security**
- Run as non-root user (UID 1001)
- Read-only root filesystem (where possible)
- Drop all capabilities
- seccomp profile enabled

### 2. **Network Policies**
- Restrict pod-to-pod communication
- Allow only necessary traffic
- Deny all by default

### 3. **Resource Limits**
- CPU and memory requests/limits
- ResourceQuota per namespace
- LimitRange for default limits

### 4. **Secret Management**
- Kubernetes secrets (encrypted at rest)
- External Secrets Operator support
- AWS Secrets Manager integration

### 5. **SSL/TLS**
- HTTPS-only with SSL redirect
- TLS 1.2+ enforcement
- AWS ACM or Let's Encrypt certificates

## 📈 Auto-Scaling

### Horizontal Pod Autoscaler (HPA)

**Backend API**:
- Min replicas: 3
- Max replicas: 20
- Target CPU: 70%
- Target Memory: 80%

**Frontend**:
- Min replicas: 3
- Max replicas: 15
- Target CPU: 70%
- Target Memory: 80%

### Scale Down Behavior
- Stabilization window: 5 minutes
- Max scale down: 50% of current pods

### Scale Up Behavior
- Stabilization window: 1 minute
- Max scale up: 100% (double current pods)

## 🔄 Rolling Updates

Zero-downtime deployments:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1           # Add 1 new pod
    maxUnavailable: 0     # Don't remove any pods
```

### Pod Disruption Budget

Minimum 2 pods always available during:
- Node maintenance
- Cluster upgrades
- Voluntary disruptions

## 💾 Persistent Storage

### PostgreSQL Storage

- **StorageClass**: `gp3` (AWS EBS)
- **Size**: 100 GB
- **Access Mode**: ReadWriteOnce
- **Backup**: Automated snapshots (configure separately)

### Redis Storage

- **Development**: EmptyDir (ephemeral)
- **Production**: Use Redis Sentinel with PVC or ElastiCache

## 🌐 Ingress Configuration

### AWS ALB Ingress

Features:
- Internet-facing Application Load Balancer
- SSL termination with ACM certificate
- HTTP to HTTPS redirect
- Health checks with configurable thresholds
- Cross-zone load balancing

### NGINX Ingress

Features:
- SSL with Let's Encrypt (cert-manager)
- HTTP/2 support
- WebSocket support
- Request body size limits

## 🔧 Troubleshooting

### Pod not starting

```bash
# Check pod status
kubectl describe pod <POD_NAME> -n smart-ai-tutor

# Check logs
kubectl logs <POD_NAME> -n smart-ai-tutor --previous

# Check events
kubectl get events -n smart-ai-tutor --sort-by='.lastTimestamp'
```

### Database connection issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15-alpine --restart=Never -- \
  psql -h postgres-service -U smart_tutor_user -d smart_tutor

# Check PostgreSQL logs
kubectl logs -n smart-ai-tutor -l component=postgres
```

### Ingress not working

```bash
# Check ingress status
kubectl describe ingress smart-ai-tutor-ingress -n smart-ai-tutor

# Check ALB controller logs
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Check NGINX ingress logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

### HPA not scaling

```bash
# Check HPA status
kubectl describe hpa backend-api-hpa -n smart-ai-tutor

# Check metrics server
kubectl top nodes
kubectl top pods -n smart-ai-tutor

# If metrics server not installed:
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

## 🚀 Production Checklist

- [ ] Container images built and pushed to registry
- [ ] All secrets created (use AWS Secrets Manager in production)
- [ ] Ingress controller installed
- [ ] cert-manager installed (for NGINX ingress)
- [ ] Metrics server installed
- [ ] ACM certificate created (for AWS ALB)
- [ ] DNS records configured
- [ ] Resource quotas appropriate for workload
- [ ] Backup strategy configured
- [ ] Monitoring and alerting configured
- [ ] Log aggregation configured
- [ ] Network policies tested
- [ ] Disaster recovery plan documented
- [ ] SLOs and SLIs defined

## 📚 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [AWS ALB Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [NGINX Ingress](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager](https://cert-manager.io/)
- [External Secrets Operator](https://external-secrets.io/)
- [Prometheus Operator](https://prometheus-operator.dev/)

## 🆘 Support

For issues or questions:
- Create an issue in the repository
- Check the [PLATFORM_ENGINEERING_AUDIT.md](../PLATFORM_ENGINEERING_AUDIT.md) for detailed analysis
- Refer to [SRE runbooks](../docs/runbooks/) (when created)

---

**Last Updated**: 2025-12-28
**Version**: 1.0.0
**Maintained By**: Platform Engineering Team
