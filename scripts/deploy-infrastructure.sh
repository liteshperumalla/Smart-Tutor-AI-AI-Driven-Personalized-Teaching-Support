#!/bin/bash

# ======================================
# AWS Infrastructure Deployment Script
# ======================================
# This script deploys the complete AWS infrastructure for Smart AI Tutor
#
# Usage:
#   ./scripts/deploy-infrastructure.sh <environment>
#
# Example:
#   ./scripts/deploy-infrastructure.sh dev
#   ./scripts/deploy-infrastructure.sh prod

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check arguments
if [ $# -eq 0 ]; then
    log_error "Environment argument required"
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev"
    exit 1
fi

ENVIRONMENT=$1

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Valid environments: dev, staging, prod"
    exit 1
fi

log_info "Deploying infrastructure for environment: $ENVIRONMENT"

# Check prerequisites
log_info "Checking prerequisites..."

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed"
    echo "Install it from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    log_error "Terraform is not installed"
    echo "Install it from: https://www.terraform.io/downloads"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    log_error "jq is not installed"
    echo "Install it: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

log_success "All prerequisites installed"

# Check AWS credentials
log_info "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
log_success "AWS Account: $AWS_ACCOUNT_ID, Region: $AWS_REGION"

# Navigate to terraform directory
cd terraform

# Initialize Terraform backend
log_info "Setting up Terraform backend..."

BACKEND_BUCKET="smart-tutor-terraform-state-${AWS_ACCOUNT_ID}"
BACKEND_TABLE="smart-tutor-terraform-locks"

# Create S3 bucket for state if it doesn't exist
if ! aws s3 ls "s3://${BACKEND_BUCKET}" 2>/dev/null; then
    log_warning "Creating S3 bucket for Terraform state: ${BACKEND_BUCKET}"
    aws s3 mb "s3://${BACKEND_BUCKET}" --region "${AWS_REGION}"

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${BACKEND_BUCKET}" \
        --versioning-configuration Status=Enabled

    # Enable encryption
    aws s3api put-bucket-encryption \
        --bucket "${BACKEND_BUCKET}" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'

    # Block public access
    aws s3api put-public-access-block \
        --bucket "${BACKEND_BUCKET}" \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

    log_success "Created S3 bucket: ${BACKEND_BUCKET}"
else
    log_info "S3 bucket already exists: ${BACKEND_BUCKET}"
fi

# Create DynamoDB table for state locking if it doesn't exist
if ! aws dynamodb describe-table --table-name "${BACKEND_TABLE}" &>/dev/null; then
    log_warning "Creating DynamoDB table for state locking: ${BACKEND_TABLE}"
    aws dynamodb create-table \
        --table-name "${BACKEND_TABLE}" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "${AWS_REGION}"

    log_info "Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name "${BACKEND_TABLE}"
    log_success "Created DynamoDB table: ${BACKEND_TABLE}"
else
    log_info "DynamoDB table already exists: ${BACKEND_TABLE}"
fi

# Initialize Terraform
log_info "Initializing Terraform..."
terraform init \
    -backend-config="bucket=${BACKEND_BUCKET}" \
    -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
    -backend-config="region=${AWS_REGION}" \
    -backend-config="dynamodb_table=${BACKEND_TABLE}" \
    -backend-config="encrypt=true"

log_success "Terraform initialized"

# Select or create workspace
log_info "Setting up Terraform workspace: ${ENVIRONMENT}"
if terraform workspace list | grep -q "${ENVIRONMENT}"; then
    terraform workspace select "${ENVIRONMENT}"
else
    terraform workspace new "${ENVIRONMENT}"
fi

log_success "Workspace selected: ${ENVIRONMENT}"

# Create tfvars file if it doesn't exist
TFVARS_FILE="environments/${ENVIRONMENT}.tfvars"
if [ ! -f "${TFVARS_FILE}" ]; then
    log_warning "Creating tfvars file: ${TFVARS_FILE}"
    mkdir -p environments

    cat > "${TFVARS_FILE}" <<EOF
# ${ENVIRONMENT} Environment Configuration
project_name   = "smart-tutor"
environment    = "${ENVIRONMENT}"
aws_region     = "${AWS_REGION}"
aws_account_id = "${AWS_ACCOUNT_ID}"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"

# RDS Configuration
rds_instance_class         = "$([ "$ENVIRONMENT" == "prod" ] && echo "db.t4g.medium" || echo "db.t4g.micro")"
rds_allocated_storage      = $([ "$ENVIRONMENT" == "prod" ] && echo "100" || echo "20")
rds_multi_az               = $([ "$ENVIRONMENT" == "prod" ] && echo "true" || echo "false")
rds_backup_retention_period = $([ "$ENVIRONMENT" == "prod" ] && echo "7" || echo "3")

# ElastiCache Configuration
redis_node_type       = "$([ "$ENVIRONMENT" == "prod" ] && echo "cache.t4g.medium" || echo "cache.t4g.micro")"
redis_num_cache_nodes = $([ "$ENVIRONMENT" == "prod" ] && echo "2" || echo "1")

# DynamoDB Configuration
dynamodb_billing_mode = "PAY_PER_REQUEST"

# Tags
tags = {
  Environment = "${ENVIRONMENT}"
  ManagedBy   = "Terraform"
  Project     = "Smart AI Tutor"
}
EOF

    log_success "Created tfvars file: ${TFVARS_FILE}"
    log_warning "Please review and update ${TFVARS_FILE} with your specific configuration"
    read -p "Press Enter to continue or Ctrl+C to exit and edit the file..."
fi

# Validate Terraform configuration
log_info "Validating Terraform configuration..."
terraform validate
log_success "Configuration is valid"

# Plan the deployment
log_info "Planning infrastructure deployment..."
terraform plan \
    -var-file="${TFVARS_FILE}" \
    -out="tfplan-${ENVIRONMENT}"

log_success "Plan created successfully"

# Ask for confirmation
echo ""
log_warning "About to deploy infrastructure to AWS"
echo "Environment: ${ENVIRONMENT}"
echo "Account: ${AWS_ACCOUNT_ID}"
echo "Region: ${AWS_REGION}"
echo ""
read -p "Do you want to proceed with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Deployment cancelled"
    exit 0
fi

# Apply the plan
log_info "Applying Terraform plan..."
terraform apply "tfplan-${ENVIRONMENT}"

log_success "Infrastructure deployed successfully!"

# Output important information
log_info "Retrieving outputs..."
echo ""
echo "=========================================="
echo "Deployment Complete"
echo "=========================================="
terraform output

# Clean up plan file
rm -f "tfplan-${ENVIRONMENT}"

log_success "Deployment script completed successfully!"
log_info "Next steps:"
echo "  1. Review the outputs above"
echo "  2. Update application configuration with new endpoints"
echo "  3. Deploy application containers to ECS"
echo "  4. Run smoke tests to verify deployment"
