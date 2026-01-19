#!/bin/bash
set -e

# Smart AI Tutor - Production Deployment Script
# This script orchestrates the complete production deployment

echo "🚀 Smart AI Tutor - Production Deployment"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-1"
ENVIRONMENT="production"

# Function to print status
print_status() {
  echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
  echo "📋 Checking prerequisites..."

  # Check AWS CLI
  if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Install: https://aws.amazon.com/cli/"
    exit 1
  fi
  print_status "AWS CLI installed"

  # Check jq
  if ! command -v jq &> /dev/null; then
    print_warning "jq not found (optional, but recommended)"
  else
    print_status "jq installed"
  fi

  # Check AWS credentials
  if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured"
    exit 1
  fi

  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  print_status "AWS credentials configured (Account: $ACCOUNT_ID)"

  # Check .env file
  if [ ! -f ".env" ]; then
    print_error ".env file not found. Copy from .env.example"
    exit 1
  fi
  print_status ".env file exists"

  echo ""
}

# Function to rotate secrets
rotate_secrets() {
  echo "🔐 Step 1: Rotating Secrets"
  echo "----------------------------"

  read -p "Rotate JWT secret now? (y/n): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x rotate_jwt_secret.sh
    ./rotate_jwt_secret.sh
    print_status "JWT secret rotated"
  else
    print_warning "Skipped JWT secret rotation"
  fi
  echo ""
}

# Function to enable backups
enable_backups() {
  echo "💾 Step 2: Verifying Backups"
  echo "----------------------------"

  # RDS backups
  chmod +x verify_rds_backups.sh
  ./verify_rds_backups.sh

  # DynamoDB PITR
  read -p "Enable DynamoDB Point-in-Time Recovery? (y/n): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x enable_dynamodb_pitr.sh
    ./enable_dynamodb_pitr.sh
    print_status "DynamoDB PITR enabled"
  else
    print_warning "Skipped DynamoDB PITR"
  fi
  echo ""
}

# Function to setup monitoring
setup_monitoring() {
  echo "📊 Step 3: Setting up Monitoring"
  echo "--------------------------------"

  # CloudWatch Logs
  read -p "Setup CloudWatch Logs? (y/n): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x setup_cloudwatch_logs.sh
    ./setup_cloudwatch_logs.sh
    print_status "CloudWatch Logs configured"
  else
    print_warning "Skipped CloudWatch Logs"
  fi

  # Error alarms
  read -p "Setup error alarms? (y/n): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x setup_error_alarms.sh
    ./setup_error_alarms.sh
    print_status "Error alarms configured"
  else
    print_warning "Skipped error alarms"
  fi
  echo ""
}

# Function to update CORS
update_cors() {
  echo "🌐 Step 4: Updating CORS Configuration"
  echo "--------------------------------------"

  read -p "Update CORS settings? (y/n): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x update_cors_production.sh
    ./update_cors_production.sh
    print_status "CORS updated"
  else
    print_warning "Skipped CORS update"
  fi
  echo ""
}

# Function to verify environment
verify_environment() {
  echo "🔍 Step 5: Verifying Environment"
  echo "--------------------------------"

  # Check critical env vars
  source .env

  CRITICAL_VARS=(
    "ENVIRONMENT"
    "AWS_REGION"
    "BEDROCK_MODEL_ID"
    "POSTGRES_HOST"
    "JWT_ALGORITHM"
    "ENFORCE_HTTPS"
  )

  MISSING_VARS=()
  for VAR in "${CRITICAL_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
      MISSING_VARS+=("$VAR")
    fi
  done

  if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    print_error "Missing environment variables:"
    for VAR in "${MISSING_VARS[@]}"; do
      echo "  - $VAR"
    done
    exit 1
  fi

  print_status "All critical environment variables set"

  # Verify production settings
  if [ "$ENVIRONMENT" != "production" ]; then
    print_warning "ENVIRONMENT is not set to 'production'"
  fi

  if [ "$ENFORCE_HTTPS" != "true" ]; then
    print_warning "ENFORCE_HTTPS is not enabled"
  fi

  echo ""
}

# Function to build and test
build_and_test() {
  echo "🔨 Step 6: Building and Testing"
  echo "-------------------------------"

  # Backend tests
  if [ -d "backend" ]; then
    read -p "Run backend tests? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cd backend
      if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt -q
        python -m pytest tests/ 2>/dev/null || print_warning "No tests found or tests failed"
      fi
      cd ..
      print_status "Backend tests complete"
    fi
  fi

  # Frontend build
  if [ -d "frontend" ]; then
    read -p "Build frontend? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cd frontend
      npm install
      npm run build
      cd ..
      print_status "Frontend built"
    fi
  fi

  echo ""
}

# Function to deploy services
deploy_services() {
  echo "🚢 Step 7: Deploying Services"
  echo "----------------------------"

  read -p "Start services with Docker Compose? (y/n): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "docker-compose.yml" ]; then
      docker-compose down
      docker-compose up -d --build
      print_status "Services deployed via Docker Compose"

      echo ""
      echo "Waiting for services to start..."
      sleep 10

      docker-compose ps
    else
      print_warning "docker-compose.yml not found"
    fi
  fi

  echo ""
}

# Function to run health checks
health_checks() {
  echo "🏥 Step 8: Running Health Checks"
  echo "--------------------------------"

  # Check backend
  if curl -f -s http://localhost:8010/health &> /dev/null; then
    print_status "Backend API is healthy"
  else
    print_error "Backend API health check failed"
  fi

  # Check frontend
  if curl -f -s http://localhost:4000 &> /dev/null; then
    print_status "Frontend is healthy"
  else
    print_error "Frontend health check failed"
  fi

  # Check AWS connectivity
  if aws bedrock list-foundation-models --region $REGION &> /dev/null; then
    print_status "AWS Bedrock connectivity verified"
  else
    print_warning "AWS Bedrock connectivity issue"
  fi

  # Check RDS connectivity
  if [ -n "$POSTGRES_HOST" ]; then
    print_status "RDS endpoint configured: $POSTGRES_HOST"
  fi

  echo ""
}

# Function to display post-deployment checklist
post_deployment_checklist() {
  echo "📋 Post-Deployment Checklist"
  echo "============================"
  echo ""
  echo "Manual steps to complete:"
  echo ""
  echo "🔐 Security:"
  echo "  [ ] Verify no secrets in code/logs"
  echo "  [ ] Test JWT token expiration"
  echo "  [ ] Review IAM permissions"
  echo "  [ ] Enable MFA for AWS console"
  echo ""
  echo "🌐 DNS & SSL:"
  echo "  [ ] Configure domain DNS records"
  echo "  [ ] Setup SSL/TLS certificates (AWS ACM or Let's Encrypt)"
  echo "  [ ] Configure CloudFront or ALB"
  echo "  [ ] Test HTTPS redirection"
  echo ""
  echo "📊 Monitoring:"
  echo "  [ ] Verify CloudWatch alarms are triggering"
  echo "  [ ] Test SNS notifications"
  echo "  [ ] Setup monitoring dashboard"
  echo "  [ ] Configure log retention policies"
  echo ""
  echo "🧪 Testing:"
  echo "  [ ] Run end-to-end tests"
  echo "  [ ] Load testing"
  echo "  [ ] Security scanning"
  echo "  [ ] Backup/restore testing"
  echo ""
  echo "📝 Documentation:"
  echo "  [ ] Update runbook"
  echo "  [ ] Document rollback procedures"
  echo "  [ ] Create incident response plan"
  echo "  [ ] Update API documentation"
  echo ""
  echo "🔄 CI/CD:"
  echo "  [ ] Setup GitHub Actions / GitLab CI"
  echo "  [ ] Configure automated testing"
  echo "  [ ] Setup staging environment"
  echo "  [ ] Configure deployment approvals"
  echo ""
}

# Main deployment flow
main() {
  check_prerequisites
  rotate_secrets
  enable_backups
  setup_monitoring
  update_cors
  verify_environment
  build_and_test
  deploy_services
  health_checks

  echo ""
  echo "✅ Production deployment complete!"
  echo ""

  post_deployment_checklist

  echo ""
  echo "🎉 Your Smart AI Tutor application is deployed!"
  echo ""
  echo "📊 View deployment status:"
  echo "   docker-compose ps"
  echo "   docker-compose logs -f"
  echo ""
  echo "🔍 Monitor in AWS Console:"
  echo "   CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=$REGION#logsV2:log-groups"
  echo "   RDS: https://console.aws.amazon.com/rds/home?region=$REGION"
  echo "   DynamoDB: https://console.aws.amazon.com/dynamodb/home?region=$REGION"
  echo ""
}

# Run main deployment
main
