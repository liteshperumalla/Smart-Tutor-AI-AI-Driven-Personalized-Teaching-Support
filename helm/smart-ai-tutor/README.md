# Smart AI Tutor Helm Chart

Official Helm chart for deploying Smart AI Tutor to Kubernetes.

## TL;DR

```bash
# Add the helm repository (if published)
helm repo add smart-ai-tutor https://charts.smart-ai-tutor.com
helm repo update

# Install the chart
helm install my-release smart-ai-tutor/smart-ai-tutor

# Or install from local chart
helm install my-release ./helm/smart-ai-tutor
```

## Introduction

This chart bootstraps a Smart AI Tutor deployment on a Kubernetes cluster using the Helm package manager.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.8+
- PV provisioner support in the underlying infrastructure (for PostgreSQL persistence)
- Ingress controller (AWS ALB Controller or NGINX Ingress)
- LoadBalancer support (for AWS, GCP, Azure)

## Installing the Chart

### Quick Install (Development)

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  --namespace smart-ai-tutor \
  --create-namespace \
  --values helm/smart-ai-tutor/values-dev.yaml
```

### Staging Environment

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  --namespace smart-ai-tutor-staging \
  --create-namespace \
  --values helm/smart-ai-tutor/values-staging.yaml \
  --set image.tag=v1.2.3 \
  --set ingress.tls.certificateArn=arn:aws:acm:...
```

### Production Environment

```bash
# Create secrets first
kubectl create secret generic backend-secrets \
  --from-literal=POSTGRES_PASSWORD=<PASSWORD> \
  --from-literal=JWT_SECRET_KEY=<SECRET> \
  --namespace smart-ai-tutor

# Install chart
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  --namespace smart-ai-tutor \
  --create-namespace \
  --values helm/smart-ai-tutor/values-production.yaml \
  --set image.registry=123456789.dkr.ecr.us-east-1.amazonaws.com \
  --set image.tag=v1.0.0 \
  --set ingress.tls.certificateArn=arn:aws:acm:us-east-1:123456789:certificate/xxxxx \
  --wait \
  --timeout 10m
```

## Uninstalling the Chart

```bash
helm uninstall smart-ai-tutor --namespace smart-ai-tutor
```

This command removes all the Kubernetes components associated with the chart and deletes the release.

## Configuration

### Global Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.environment` | Environment name | `production` |
| `global.domain` | Base domain for the application | `smart-ai-tutor.com` |

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.registry` | Container registry | `docker.io` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `image.pullSecrets` | Image pull secrets | `[]` |

### Backend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `backend.enabled` | Enable backend deployment | `true` |
| `backend.image.repository` | Backend image repository | `smart-ai-tutor-backend` |
| `backend.image.tag` | Backend image tag | `latest` |
| `backend.replicaCount` | Number of backend replicas | `3` |
| `backend.autoscaling.enabled` | Enable HPA | `true` |
| `backend.autoscaling.minReplicas` | Minimum replicas | `3` |
| `backend.autoscaling.maxReplicas` | Maximum replicas | `20` |
| `backend.autoscaling.targetCPUUtilizationPercentage` | Target CPU | `70` |
| `backend.autoscaling.targetMemoryUtilizationPercentage` | Target memory | `80` |
| `backend.resources.requests.cpu` | CPU request | `500m` |
| `backend.resources.requests.memory` | Memory request | `512Mi` |
| `backend.resources.limits.cpu` | CPU limit | `2000m` |
| `backend.resources.limits.memory` | Memory limit | `2Gi` |

### Frontend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `frontend.enabled` | Enable frontend deployment | `true` |
| `frontend.image.repository` | Frontend image repository | `smart-ai-tutor-frontend` |
| `frontend.image.tag` | Frontend image tag | `latest` |
| `frontend.replicaCount` | Number of frontend replicas | `3` |
| `frontend.autoscaling.enabled` | Enable HPA | `true` |
| `frontend.autoscaling.minReplicas` | Minimum replicas | `3` |
| `frontend.autoscaling.maxReplicas` | Maximum replicas | `15` |

### PostgreSQL Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgres.enabled` | Enable PostgreSQL deployment | `true` |
| `postgres.external.enabled` | Use external PostgreSQL (RDS) | `false` |
| `postgres.external.host` | External PostgreSQL host | `""` |
| `postgres.persistence.enabled` | Enable persistent storage | `true` |
| `postgres.persistence.storageClass` | Storage class name | `gp3` |
| `postgres.persistence.size` | Storage size | `100Gi` |

### Redis Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis deployment | `true` |
| `redis.external.enabled` | Use external Redis (ElastiCache) | `false` |
| `redis.external.host` | External Redis host | `""` |
| `redis.exporter.enabled` | Enable Prometheus exporter | `true` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `alb` |
| `ingress.tls.enabled` | Enable TLS | `true` |
| `ingress.tls.certificateArn` | AWS ACM certificate ARN | `""` |

### Network Policy

| Parameter | Description | Default |
|-----------|-------------|---------|
| `networkPolicy.enabled` | Enable network policies | `true` |

### Monitoring

| Parameter | Description | Default |
|-----------|-------------|---------|
| `monitoring.enabled` | Enable Prometheus monitoring | `true` |

## Environment-Specific Values

### Development (`values-dev.yaml`)

- Single replica for each service
- Auto-scaling disabled
- Reduced resource requests
- No TLS
- In-cluster PostgreSQL and Redis
- Network policies disabled

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor -f values-dev.yaml
```

### Staging (`values-staging.yaml`)

- 2 replicas minimum
- Auto-scaling enabled (up to 10 backend, 8 frontend)
- External RDS and ElastiCache
- TLS enabled with staging certificate
- Network policies enabled

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor -f values-staging.yaml
```

### Production (`values-production.yaml`)

- 3 replicas minimum
- Auto-scaling enabled (up to 20 backend, 15 frontend)
- External RDS Multi-AZ and ElastiCache Cluster
- TLS enabled with production certificate
- All security features enabled
- Resource quotas enforced

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor -f values-production.yaml
```

## Upgrading the Chart

### Update to New Version

```bash
helm upgrade smart-ai-tutor ./helm/smart-ai-tutor \
  --namespace smart-ai-tutor \
  --values values-production.yaml \
  --set image.tag=v1.1.0 \
  --wait
```

### Rollback

```bash
# List releases
helm history smart-ai-tutor --namespace smart-ai-tutor

# Rollback to previous version
helm rollback smart-ai-tutor --namespace smart-ai-tutor

# Rollback to specific revision
helm rollback smart-ai-tutor 3 --namespace smart-ai-tutor
```

## Advanced Configuration

### Using External Secrets Operator

```yaml
secrets:
  externalSecrets:
    enabled: true
    backend: secretsManager
    region: us-east-1
```

### Using IRSA (IAM Roles for Service Accounts)

```yaml
serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: "arn:aws:iam::123456789:role/smart-ai-tutor-role"
```

### Custom Image Registry

```yaml
image:
  registry: 123456789.dkr.ecr.us-east-1.amazonaws.com
  pullSecrets:
    - regcred
```

### Override Specific Values

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  --set backend.replicaCount=5 \
  --set backend.resources.requests.cpu=1000m \
  --set ingress.tls.certificateArn=arn:aws:acm:...
```

## Templates Overview

The chart includes templates for:

- **Deployments**: Backend API, Frontend
- **StatefulSets**: PostgreSQL (if not using external)
- **Services**: All components
- **Ingress**: ALB or NGINX ingress
- **HorizontalPodAutoscaler**: Backend and Frontend
- **PodDisruptionBudget**: Backend
- **NetworkPolicy**: All components
- **ConfigMaps**: Configuration for all services
- **Secrets**: Placeholder templates (create manually)
- **ResourceQuota**: Namespace-level quotas
- **ServiceAccount**: For IRSA

## Examples

### Example 1: Deploy to Minikube (Development)

```bash
# Start minikube
minikube start --cpus=4 --memory=8192

# Enable ingress
minikube addons enable ingress

# Install chart
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  -f values-dev.yaml \
  --set image.registry=localhost:5000

# Port forward
kubectl port-forward svc/smart-ai-tutor-frontend 3000:3000
```

### Example 2: Deploy to AWS EKS (Production)

```bash
# Create EKS cluster
eksctl create cluster --name smart-ai-tutor --region us-east-1

# Install AWS ALB Controller
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller//crds?ref=master"
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=smart-ai-tutor

# Install chart
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  -f values-production.yaml \
  --set image.tag=v1.0.0
```

### Example 3: Deploy with Custom Database

```bash
helm install smart-ai-tutor ./helm/smart-ai-tutor \
  --set postgres.enabled=false \
  --set postgres.external.enabled=true \
  --set postgres.external.host=my-db.rds.amazonaws.com \
  --set redis.enabled=false \
  --set redis.external.enabled=true \
  --set redis.external.host=my-redis.cache.amazonaws.com
```

## Troubleshooting

### Chart Installation Fails

```bash
# Dry run to check for errors
helm install smart-ai-tutor ./helm/smart-ai-tutor --dry-run --debug

# Lint the chart
helm lint ./helm/smart-ai-tutor
```

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n smart-ai-tutor

# Describe pod
kubectl describe pod <POD_NAME> -n smart-ai-tutor

# Check logs
kubectl logs <POD_NAME> -n smart-ai-tutor
```

### Ingress Not Working

```bash
# Check ingress
kubectl get ingress -n smart-ai-tutor
kubectl describe ingress smart-ai-tutor-ingress -n smart-ai-tutor

# Check ALB controller logs
kubectl logs -n kube-system deployment/aws-load-balancer-controller
```

## Chart Development

### Testing Locally

```bash
# Lint chart
helm lint ./helm/smart-ai-tutor

# Template chart (without installing)
helm template smart-ai-tutor ./helm/smart-ai-tutor

# Template with specific values
helm template smart-ai-tutor ./helm/smart-ai-tutor -f values-production.yaml

# Install in debug mode
helm install smart-ai-tutor ./helm/smart-ai-tutor --dry-run --debug
```

### Packaging Chart

```bash
# Package chart
helm package ./helm/smart-ai-tutor

# Generate index
helm repo index .

# Push to chart repository (e.g., ChartMuseum, Harbor)
curl --data-binary "@smart-ai-tutor-1.0.0.tgz" http://chartmuseum.example.com/api/charts
```

## Security Considerations

1. **Secrets Management**: Always use Kubernetes secrets or external secret managers (AWS Secrets Manager, Vault)
2. **Image Security**: Use specific image tags, not `latest`
3. **Network Policies**: Enable in production to restrict pod-to-pod communication
4. **RBAC**: Chart creates minimal RBAC rules by default
5. **Pod Security**: Non-root containers, dropped capabilities
6. **TLS**: Always enable TLS in production

## Contributing

Please read [CONTRIBUTING.md](../../CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/smart-ai-tutor/issues
- Documentation: https://docs.smart-ai-tutor.com
- Email: support@smart-ai-tutor.com

---

**Chart Version**: 1.0.0
**App Version**: 1.0.0
**Last Updated**: 2025-12-28
