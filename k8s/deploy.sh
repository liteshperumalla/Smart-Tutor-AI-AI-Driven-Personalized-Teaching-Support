#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="smart-ai-tutor"
REGISTRY="${REGISTRY:-<YOUR_REGISTRY>}"
VERSION="${VERSION:-latest}"
ENVIRONMENT="${ENVIRONMENT:-production}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Smart AI Tutor - K8s Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "  Namespace: ${NAMESPACE}"
echo -e "  Registry: ${REGISTRY}"
echo -e "  Version: ${VERSION}"
echo -e "  Environment: ${ENVIRONMENT}"
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found. Please install kubectl.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ kubectl found${NC}"

    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Cluster connection verified${NC}"

    # Check if images exist
    echo -e "${YELLOW}⚠ Make sure container images are built and pushed:${NC}"
    echo -e "  - ${REGISTRY}/smart-ai-tutor-backend:${VERSION}"
    echo -e "  - ${REGISTRY}/smart-ai-tutor-frontend:${VERSION}"
    echo ""
}

# Function to create namespace
create_namespace() {
    echo -e "${BLUE}Creating namespace...${NC}"
    kubectl apply -f base/namespace.yaml
    echo -e "${GREEN}✓ Namespace created${NC}"
}

# Function to create secrets
create_secrets() {
    echo -e "${BLUE}Creating secrets...${NC}"

    # Check if secrets already exist
    if kubectl get secret backend-secrets -n ${NAMESPACE} &> /dev/null; then
        echo -e "${YELLOW}⚠ backend-secrets already exists. Skipping creation.${NC}"
    else
        echo -e "${RED}❌ backend-secrets not found.${NC}"
        echo -e "${YELLOW}Please create secrets manually or use AWS Secrets Manager.${NC}"
        echo ""
        echo "Example:"
        echo "  kubectl create secret generic backend-secrets \\"
        echo "    --from-literal=POSTGRES_PASSWORD=<PASSWORD> \\"
        echo "    --from-literal=REDIS_PASSWORD=<PASSWORD> \\"
        echo "    --from-literal=JWT_SECRET_KEY=<SECRET> \\"
        echo "    --namespace ${NAMESPACE}"
        echo ""
        read -p "Have you created the secrets? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    echo -e "${GREEN}✓ Secrets verified${NC}"
}

# Function to deploy base resources
deploy_base() {
    echo -e "${BLUE}Deploying base resources...${NC}"
    kubectl apply -f base/resource-quota.yaml
    echo -e "${GREEN}✓ Resource quotas applied${NC}"
}

# Function to deploy database
deploy_database() {
    echo -e "${BLUE}Deploying PostgreSQL...${NC}"
    kubectl apply -f postgres/

    # Wait for PostgreSQL to be ready
    echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l component=postgres -n ${NAMESPACE} --timeout=300s
    echo -e "${GREEN}✓ PostgreSQL deployed and ready${NC}"
}

# Function to deploy cache
deploy_cache() {
    echo -e "${BLUE}Deploying Redis...${NC}"
    kubectl apply -f redis/

    # Wait for Redis to be ready
    echo -e "${YELLOW}Waiting for Redis to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l component=redis -n ${NAMESPACE} --timeout=120s
    echo -e "${GREEN}✓ Redis deployed and ready${NC}"
}

# Function to deploy backend
deploy_backend() {
    echo -e "${BLUE}Deploying Backend API...${NC}"
    kubectl apply -f backend/

    # Wait for backend to be ready
    echo -e "${YELLOW}Waiting for Backend API to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l component=backend -n ${NAMESPACE} --timeout=300s
    echo -e "${GREEN}✓ Backend API deployed and ready${NC}"
}

# Function to deploy frontend
deploy_frontend() {
    echo -e "${BLUE}Deploying Frontend...${NC}"
    kubectl apply -f frontend/

    # Wait for frontend to be ready
    echo -e "${YELLOW}Waiting for Frontend to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l component=frontend -n ${NAMESPACE} --timeout=300s
    echo -e "${GREEN}✓ Frontend deployed and ready${NC}"
}

# Function to deploy ingress
deploy_ingress() {
    echo -e "${BLUE}Deploying Ingress...${NC}"

    # Check if ingress controller exists
    if ! kubectl get ingressclass &> /dev/null; then
        echo -e "${YELLOW}⚠ No ingress controller found. Please install ALB or NGINX ingress controller first.${NC}"
        echo ""
        echo "AWS ALB Controller:"
        echo "  https://kubernetes-sigs.github.io/aws-load-balancer-controller/"
        echo ""
        echo "NGINX Ingress:"
        echo "  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml"
        echo ""
        read -p "Continue without ingress? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        kubectl apply -f ingress/
        echo -e "${GREEN}✓ Ingress deployed${NC}"
    fi
}

# Function to verify deployment
verify_deployment() {
    echo -e "${BLUE}Verifying deployment...${NC}"
    echo ""

    # Get all resources
    echo -e "${GREEN}Pods:${NC}"
    kubectl get pods -n ${NAMESPACE}
    echo ""

    echo -e "${GREEN}Services:${NC}"
    kubectl get svc -n ${NAMESPACE}
    echo ""

    echo -e "${GREEN}Ingress:${NC}"
    kubectl get ingress -n ${NAMESPACE}
    echo ""

    echo -e "${GREEN}HPA:${NC}"
    kubectl get hpa -n ${NAMESPACE}
    echo ""

    # Check if all pods are running
    NOT_RUNNING=$(kubectl get pods -n ${NAMESPACE} --field-selector=status.phase!=Running -o name | wc -l)
    if [ $NOT_RUNNING -gt 0 ]; then
        echo -e "${YELLOW}⚠ Warning: Some pods are not running${NC}"
        kubectl get pods -n ${NAMESPACE} --field-selector=status.phase!=Running
    else
        echo -e "${GREEN}✓ All pods are running${NC}"
    fi
}

# Function to show access information
show_access_info() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Deployment Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Get ingress URL
    INGRESS_URL=$(kubectl get ingress smart-ai-tutor-ingress -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "Not available yet")

    echo -e "${GREEN}Access Information:${NC}"
    echo -e "  Frontend: https://smart-ai-tutor.com"
    echo -e "  Backend API: https://api.smart-ai-tutor.com"
    echo -e "  Load Balancer: ${INGRESS_URL}"
    echo ""

    echo -e "${GREEN}Useful Commands:${NC}"
    echo -e "  View pods:    kubectl get pods -n ${NAMESPACE}"
    echo -e "  View logs:    kubectl logs -n ${NAMESPACE} -l component=backend --tail=100"
    echo -e "  View metrics: kubectl top pods -n ${NAMESPACE}"
    echo -e "  Shell into:   kubectl exec -it -n ${NAMESPACE} <POD_NAME> -- /bin/sh"
    echo ""

    echo -e "${YELLOW}Next Steps:${NC}"
    echo -e "  1. Configure DNS to point to the load balancer"
    echo -e "  2. Verify health checks: https://api.smart-ai-tutor.com/health"
    echo -e "  3. Check metrics: https://api.smart-ai-tutor.com/metrics"
    echo -e "  4. Set up monitoring alerts in Prometheus"
    echo -e "  5. Configure automated backups"
    echo ""
}

# Main deployment flow
main() {
    check_prerequisites
    create_namespace
    create_secrets
    deploy_base
    deploy_database
    deploy_cache
    deploy_backend
    deploy_frontend
    deploy_ingress
    verify_deployment
    show_access_info
}

# Run deployment
main
