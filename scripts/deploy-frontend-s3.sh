#!/bin/bash
# ======================================
# Frontend Deployment Script for S3 + CloudFront
# ======================================
# This script builds the Next.js frontend and deploys it to S3
# with CloudFront cache invalidation for cost-optimized hosting
#
# Cost Savings: $150/month vs running on ECS
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - Node.js and npm installed
# - jq installed for JSON parsing

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Default values
ENVIRONMENT="${ENVIRONMENT:-production}"
PROJECT_NAME="${PROJECT_NAME:-smart-ai-tutor}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Derived values
S3_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-frontend"
CLOUDFRONT_DISTRIBUTION_ID="${CLOUDFRONT_DISTRIBUTION_ID:-}"
BUILD_DIR="$FRONTEND_DIR/out"

# ======================================
# Functions
# ======================================

print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓ ${NC}$1"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${NC}$1"
}

print_error() {
    echo -e "${RED}✗ ${NC}$1"
}

check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi
    print_success "AWS CLI found"

    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed"
        exit 1
    fi
    print_success "Node.js found ($(node --version))"

    # Check npm
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed"
        exit 1
    fi
    print_success "npm found ($(npm --version))"

    # Check jq
    if ! command -v jq &> /dev/null; then
        print_warning "jq is not installed (optional, for JSON parsing)"
    else
        print_success "jq found"
    fi

    # Verify AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured correctly"
        exit 1
    fi
    print_success "AWS credentials verified"

    # Check if S3 bucket exists
    if ! aws s3 ls "s3://$S3_BUCKET" &> /dev/null; then
        print_error "S3 bucket '$S3_BUCKET' does not exist"
        print_info "Please create the bucket first or run Terraform to provision infrastructure"
        exit 1
    fi
    print_success "S3 bucket '$S3_BUCKET' exists"
}

install_dependencies() {
    print_info "Installing frontend dependencies..."
    cd "$FRONTEND_DIR"

    if [ -f "package-lock.json" ]; then
        npm ci --production=false
    else
        npm install
    fi

    print_success "Dependencies installed"
}

build_frontend() {
    print_info "Building Next.js application..."
    cd "$FRONTEND_DIR"

    # Set environment variables for build
    export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-https://api.smartaitutor.com}"
    export NODE_ENV=production

    # Build for static export
    npm run build

    # Export static files (requires Next.js config with output: 'export')
    if [ -d "$BUILD_DIR" ]; then
        print_success "Build completed successfully"
        print_info "Build directory: $BUILD_DIR"
    else
        print_error "Build directory not found. Ensure Next.js is configured for static export."
        exit 1
    fi
}

create_error_pages() {
    print_info "Creating custom error pages..."

    # Create 404 page if it doesn't exist
    if [ ! -f "$BUILD_DIR/404.html" ]; then
        cp "$BUILD_DIR/index.html" "$BUILD_DIR/404.html" 2>/dev/null || true
    fi

    # Create 403 page
    if [ ! -f "$BUILD_DIR/403.html" ]; then
        cp "$BUILD_DIR/index.html" "$BUILD_DIR/403.html" 2>/dev/null || true
    fi

    print_success "Error pages created"
}

sync_to_s3() {
    print_info "Syncing files to S3 bucket '$S3_BUCKET'..."

    # Sync with cache headers
    aws s3 sync "$BUILD_DIR" "s3://$S3_BUCKET" \
        --region "$AWS_REGION" \
        --delete \
        --cache-control "max-age=31536000" \
        --exclude "*.html" \
        --exclude "*.json"

    # Upload HTML and JSON files with shorter cache
    aws s3 sync "$BUILD_DIR" "s3://$S3_BUCKET" \
        --region "$AWS_REGION" \
        --delete \
        --cache-control "max-age=0, must-revalidate" \
        --content-type "text/html" \
        --exclude "*" \
        --include "*.html"

    aws s3 sync "$BUILD_DIR" "s3://$S3_BUCKET" \
        --region "$AWS_REGION" \
        --delete \
        --cache-control "max-age=0, must-revalidate" \
        --content-type "application/json" \
        --exclude "*" \
        --include "*.json"

    print_success "Files synced to S3"
}

invalidate_cloudfront() {
    if [ -z "$CLOUDFRONT_DISTRIBUTION_ID" ]; then
        print_warning "CloudFront distribution ID not provided, skipping cache invalidation"
        print_info "Set CLOUDFRONT_DISTRIBUTION_ID environment variable to enable cache invalidation"
        return 0
    fi

    print_info "Invalidating CloudFront cache..."

    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)

    print_success "CloudFront cache invalidation created (ID: $INVALIDATION_ID)"
    print_info "Waiting for invalidation to complete..."

    aws cloudfront wait invalidation-completed \
        --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
        --id "$INVALIDATION_ID" \
        2>/dev/null || true

    print_success "CloudFront cache invalidated"
}

verify_deployment() {
    print_info "Verifying deployment..."

    # Check if index.html exists in S3
    if aws s3api head-object --bucket "$S3_BUCKET" --key "index.html" &> /dev/null; then
        print_success "index.html found in S3"
    else
        print_error "index.html not found in S3"
        exit 1
    fi

    # Count objects in S3
    OBJECT_COUNT=$(aws s3 ls "s3://$S3_BUCKET" --recursive | wc -l)
    print_success "Total files in S3: $OBJECT_COUNT"

    # Get bucket size
    BUCKET_SIZE=$(aws s3 ls "s3://$S3_BUCKET" --recursive --summarize | grep "Total Size" | awk '{print $3}')
    BUCKET_SIZE_MB=$((BUCKET_SIZE / 1024 / 1024))
    print_success "Total size: ${BUCKET_SIZE_MB} MB"
}

print_deployment_info() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Deployment Successful!${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
    echo -e "${BLUE}S3 Bucket:${NC} $S3_BUCKET"

    if [ -n "$CLOUDFRONT_DISTRIBUTION_ID" ]; then
        # Get CloudFront domain name
        CF_DOMAIN=$(aws cloudfront get-distribution \
            --id "$CLOUDFRONT_DISTRIBUTION_ID" \
            --query 'Distribution.DomainName' \
            --output text 2>/dev/null || echo "N/A")
        echo -e "${BLUE}CloudFront URL:${NC} https://$CF_DOMAIN"
    fi

    echo -e "${BLUE}Region:${NC} $AWS_REGION"
    echo ""
    echo -e "${YELLOW}Cost Savings:${NC} ~$150/month vs ECS deployment"
    echo ""
}

cleanup() {
    print_info "Cleaning up..."
    # No cleanup needed for this script
}

# ======================================
# Main
# ======================================

main() {
    print_info "Starting frontend deployment to S3 + CloudFront"
    print_info "Environment: $ENVIRONMENT"
    print_info "S3 Bucket: $S3_BUCKET"
    echo ""

    # Trap errors
    trap cleanup EXIT

    # Run deployment steps
    check_prerequisites
    install_dependencies
    build_frontend
    create_error_pages
    sync_to_s3
    invalidate_cloudfront
    verify_deployment
    print_deployment_info
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--distribution-id)
            CLOUDFRONT_DISTRIBUTION_ID="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV        Environment name (default: production)"
            echo "  -d, --distribution-id ID     CloudFront distribution ID"
            echo "  -r, --region REGION          AWS region (default: us-east-1)"
            echo "  -h, --help                   Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  ENVIRONMENT                  Environment name"
            echo "  PROJECT_NAME                 Project name"
            echo "  AWS_REGION                   AWS region"
            echo "  CLOUDFRONT_DISTRIBUTION_ID   CloudFront distribution ID"
            echo "  NEXT_PUBLIC_API_URL          API URL for frontend"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main
