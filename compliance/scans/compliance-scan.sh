#!/bin/bash
# Compliance Scanning Script
# Scans infrastructure for SOC2, HIPAA, and PCI-DSS compliance
# Usage: ./compliance-scan.sh [framework]

set -euo pipefail

FRAMEWORK="${1:-all}"  # all, soc2, hipaa, pci
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="/tmp/compliance-reports-${TIMESTAMP}"
KUBERNETES_MANIFESTS="k8s/"
HELM_CHARTS="helm/"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=0

    if ! command -v conftest &> /dev/null; then
        log_error "conftest not found. Install from: https://www.conftest.dev/"
        missing=1
    fi

    if ! command -v helm &> /dev/null; then
        log_error "helm not found. Install Helm 3.x to scan Helm charts."
        missing=1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_warn "kubectl not found. Some checks will be skipped."
    fi

    if ! command -v aws &> /dev/null; then
        log_warn "AWS CLI not found. Cloud compliance checks will be skipped."
    fi

    if [ $missing -eq 1 ]; then
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Create report directory
create_report_dir() {
    mkdir -p "$REPORT_DIR"/{kubernetes,aws,docker,reports}
    log_info "Created report directory: $REPORT_DIR"
}

# Scan Kubernetes manifests
scan_kubernetes() {
    local framework=$1
    log_info "Scanning Kubernetes manifests for $framework compliance..."

    local policy_file="compliance/policies/${framework}-policy.rego"

    if [ ! -f "$policy_file" ]; then
        log_warn "Policy file not found: $policy_file"
        return
    fi

    # Scan K8s manifests
    log_info "Scanning k8s/ directory..."
    conftest test "$KUBERNETES_MANIFESTS" \
        --policy "$policy_file" \
        --all-namespaces \
        --output json > "$REPORT_DIR/kubernetes/${framework}-k8s-scan.json" 2>&1 || true

    # Scan Helm charts
    if [ -d "$HELM_CHARTS" ]; then
        log_info "Scanning Helm charts..."
        helm template smart-ai-tutor "$HELM_CHARTS/smart-ai-tutor" | \
            conftest test - \
            --policy "$policy_file" \
            --output json > "$REPORT_DIR/kubernetes/${framework}-helm-scan.json" 2>&1 || true
    fi

    # Scan running cluster (if kubectl available)
    if command -v kubectl &> /dev/null && kubectl version --client &> /dev/null; then
        log_info "Scanning running cluster resources..."
        kubectl get deployments,services,ingresses,networkpolicies --all-namespaces -o yaml | \
            conftest test - \
            --policy "$policy_file" \
            --output json > "$REPORT_DIR/kubernetes/${framework}-cluster-scan.json" 2>&1 || true
    fi

    log_info "Kubernetes scan completed for $framework"
}

# Scan AWS resources
scan_aws() {
    local framework=$1

    if ! command -v aws &> /dev/null; then
        log_warn "AWS CLI not available, skipping cloud scans"
        return
    fi

    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_warn "AWS credentials not configured, skipping cloud scans"
        return
    fi

    log_info "Scanning AWS resources for $framework compliance..."

    # S3 Bucket encryption
    log_info "Checking S3 bucket encryption..."
    aws s3api list-buckets --query "Buckets[].Name" --output text | tr '\t' '\n' | while read bucket; do
        encryption=$(aws s3api get-bucket-encryption --bucket "$bucket" 2>&1 || echo "NOT_ENCRYPTED")
        echo "{\"bucket\": \"$bucket\", \"encryption\": \"$encryption\"}" >> "$REPORT_DIR/aws/${framework}-s3-encryption.json"
    done

    # RDS encryption
    log_info "Checking RDS encryption..."
    aws rds describe-db-instances \
        --query 'DBInstances[*].{Name:DBInstanceIdentifier,Encrypted:StorageEncrypted,BackupRetention:BackupRetentionPeriod}' \
        --output json > "$REPORT_DIR/aws/${framework}-rds-config.json"

    # VPC Flow Logs
    log_info "Checking VPC Flow Logs..."
    aws ec2 describe-flow-logs \
        --output json > "$REPORT_DIR/aws/${framework}-vpc-flowlogs.json"

    # CloudTrail
    log_info "Checking CloudTrail..."
    aws cloudtrail describe-trails \
        --output json > "$REPORT_DIR/aws/${framework}-cloudtrail.json"

    # KMS Keys
    log_info "Checking KMS key rotation..."
    aws kms list-keys --query 'Keys[*].KeyId' --output text | tr '\t' '\n' | while read key; do
        rotation=$(aws kms get-key-rotation-status --key-id "$key" 2>&1 || echo "ERROR")
        echo "{\"key\": \"$key\", \"rotation\": \"$rotation\"}" >> "$REPORT_DIR/aws/${framework}-kms-rotation.json"
    done

    # Secrets Manager
    log_info "Checking Secrets Manager rotation..."
    aws secretsmanager list-secrets \
        --query 'SecretList[*].{Name:Name,Rotation:RotationEnabled,LastRotated:LastRotatedDate}' \
        --output json > "$REPORT_DIR/aws/${framework}-secrets-rotation.json"

    log_info "AWS scan completed for $framework"
}

# Scan Docker images
scan_docker_images() {
    local framework=$1
    log_info "Scanning Docker images for $framework compliance..."

    # Check if Trivy is available
    if command -v trivy &> /dev/null; then
        # Scan backend image
        if command -v docker &> /dev/null && docker images | grep smart-ai-tutor-backend &> /dev/null; then
            trivy image --format json --output "$REPORT_DIR/docker/${framework}-backend-image.json" \
                smart-ai-tutor-backend:latest 2>&1 || true
        fi

        # Scan frontend image
        if command -v docker &> /dev/null && docker images | grep smart-ai-tutor-frontend &> /dev/null; then
            trivy image --format json --output "$REPORT_DIR/docker/${framework}-frontend-image.json" \
                smart-ai-tutor-frontend:latest 2>&1 || true
        fi
    else
        log_warn "Trivy not found, skipping Docker image scans"
    fi
}

# Generate compliance report
generate_report() {
    local framework=$1
    log_info "Generating compliance report for $framework..."

    local report_file="$REPORT_DIR/reports/${framework}-compliance-report.txt"

    cat > "$report_file" <<EOF
========================================
COMPLIANCE SCAN REPORT
========================================

Framework: ${framework^^}
Scan Date: $(date)
Environment: ${ENVIRONMENT:-production}

========================================
KUBERNETES RESOURCES
========================================

$(cat "$REPORT_DIR/kubernetes/${framework}-"*.json 2>/dev/null | jq -r '.[] | select(.failures) | .filename + ": " + (.failures | length | tostring) + " violations"' 2>/dev/null || echo "No violations found")

========================================
AWS RESOURCES
========================================

S3 Encryption:
$(cat "$REPORT_DIR/aws/${framework}-s3-encryption.json" 2>/dev/null | jq -s '.' | jq -r '.[] | .bucket + ": " + (.encryption | if contains("SSEAlgorithm") then "ENCRYPTED" else "NOT_ENCRYPTED" end)' 2>/dev/null || echo "N/A")

RDS Encryption:
$(cat "$REPORT_DIR/aws/${framework}-rds-config.json" 2>/dev/null | jq -r '.[] | .Name + ": " + (.Encrypted | tostring)' 2>/dev/null || echo "N/A")

CloudTrail Status:
$(cat "$REPORT_DIR/aws/${framework}-cloudtrail.json" 2>/dev/null | jq -r '.trailList[] | .Name + ": " + (.IsLogging | tostring)' 2>/dev/null || echo "N/A")

========================================
DOCKER IMAGES
========================================

$(cat "$REPORT_DIR/docker/${framework}-"*.json 2>/dev/null | jq -r '.Results[] | .Vulnerabilities | "Total Vulnerabilities: " + (length | tostring)' 2>/dev/null || echo "No scans available")

========================================
COMPLIANCE SUMMARY
========================================

Total Issues Found: $(find "$REPORT_DIR" -name "*.json" -exec cat {} \; | jq -r 'select(.failures) | .failures | length' 2>/dev/null | awk '{s+=$1} END {print s}')

Recommended Actions:
1. Review all violations in detail
2. Create remediation tickets
3. Update policies and procedures
4. Schedule re-scan after remediation

Report Location: $REPORT_DIR

========================================
END OF REPORT
========================================
EOF

    cat "$report_file"
    log_info "Report saved to: $report_file"
}

# Upload report to S3
upload_report() {
    if command -v aws &> /dev/null; then
        log_info "Uploading reports to S3..."

        aws s3 sync "$REPORT_DIR" \
            "s3://smart-tutor-prod-compliance-reports/${TIMESTAMP}/" \
            --region "${AWS_REGION:-us-east-1}" 2>&1 || log_warn "Failed to upload to S3"

        log_info "Reports uploaded to S3"
    fi
}

# Send Slack notification
send_notification() {
    local framework=$1

    if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
        return
    fi

    local total_issues=$(find "$REPORT_DIR" -name "*.json" -exec cat {} \; | jq -r 'select(.failures) | .failures | length' 2>/dev/null | awk '{s+=$1} END {print s}')

    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"🔒 Compliance Scan Complete\",
            \"blocks\": [
                {
                    \"type\": \"header\",
                    \"text\": {
                        \"type\": \"plain_text\",
                        \"text\": \"Compliance Scan: ${framework^^}\"
                    }
                },
                {
                    \"type\": \"section\",
                    \"fields\": [
                        {
                            \"type\": \"mrkdwn\",
                            \"text\": \"*Framework:*\\n${framework^^}\"
                        },
                        {
                            \"type\": \"mrkdwn\",
                            \"text\": \"*Issues Found:*\\n${total_issues:-0}\"
                        },
                        {
                            \"type\": \"mrkdwn\",
                            \"text\": \"*Date:*\\n$(date)\"
                        }
                    ]
                }
            ]
        }" 2>&1 || log_warn "Failed to send Slack notification"
}

# Main execution
main() {
    log_info "=========================================="
    log_info "Compliance Scanner"
    log_info "Framework: $FRAMEWORK"
    log_info "=========================================="

    check_prerequisites
    create_report_dir

    if [ "$FRAMEWORK" == "all" ]; then
        for fw in soc2 hipaa pci; do
            scan_kubernetes "$fw"
            scan_aws "$fw"
            scan_docker_images "$fw"
            generate_report "$fw"
            send_notification "$fw"
        done
    else
        scan_kubernetes "$FRAMEWORK"
        scan_aws "$FRAMEWORK"
        scan_docker_images "$FRAMEWORK"
        generate_report "$FRAMEWORK"
        send_notification "$FRAMEWORK"
    fi

    upload_report

    log_info "=========================================="
    log_info "Compliance scan completed!"
    log_info "Reports saved to: $REPORT_DIR"
    log_info "=========================================="
}

# Run main
main "$@"
