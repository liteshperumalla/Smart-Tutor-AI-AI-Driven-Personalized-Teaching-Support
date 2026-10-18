#!/bin/bash

# Complete AWS Production Setup for Smart AI Tutor
# Migrates all local resources to AWS

set -e  # Exit on error

echo "=========================================="
echo "  AWS Production Setup - Smart AI Tutor"
echo "=========================================="
echo ""

# Configuration
AWS_REGION="us-east-1"
S3_DOCUMENTS_BUCKET="smart-ai-tutor-docs"
S3_UPLOADS_BUCKET="smart-ai-tutor-uploads"
S3_LOGS_BUCKET="smart-ai-tutor-logs"

echo "Step 1: Create S3 Buckets"
echo "-------------------------"

# Documents bucket (already exists from Phase 4)
aws s3api head-bucket --bucket $S3_DOCUMENTS_BUCKET --region $AWS_REGION 2>/dev/null \
  && echo "✅ Documents bucket exists: $S3_DOCUMENTS_BUCKET" \
  || {
    aws s3api create-bucket --bucket $S3_DOCUMENTS_BUCKET --region $AWS_REGION
    echo "✅ Created documents bucket: $S3_DOCUMENTS_BUCKET"
  }

# Uploads bucket
aws s3api head-bucket --bucket $S3_UPLOADS_BUCKET --region $AWS_REGION 2>/dev/null \
  && echo "✅ Uploads bucket exists: $S3_UPLOADS_BUCKET" \
  || {
    aws s3api create-bucket --bucket $S3_UPLOADS_BUCKET --region $AWS_REGION
    echo "✅ Created uploads bucket: $S3_UPLOADS_BUCKET"
  }

# Logs bucket (for cost tracking, application logs)
aws s3api head-bucket --bucket $S3_LOGS_BUCKET --region $AWS_REGION 2>/dev/null \
  && echo "✅ Logs bucket exists: $S3_LOGS_BUCKET" \
  || {
    aws s3api create-bucket --bucket $S3_LOGS_BUCKET --region $AWS_REGION
    echo "✅ Created logs bucket: $S3_LOGS_BUCKET"
  }

echo ""
echo "Step 2: Configure S3 Lifecycle Policies"
echo "----------------------------------------"

# Cost tracking logs lifecycle (archive to Glacier after 90 days, delete after 2 years)
cat > /tmp/cost-lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "Id": "ArchiveOldCostLogs",
      "Status": "Enabled",
      "Prefix": "cost_tracking/",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 730
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket $S3_LOGS_BUCKET \
  --lifecycle-configuration file:///tmp/cost-lifecycle.json \
  && echo "✅ Applied lifecycle policy to logs bucket"

echo ""
echo "Step 3: Enable S3 Versioning"
echo "-----------------------------"

aws s3api put-bucket-versioning \
  --bucket $S3_DOCUMENTS_BUCKET \
  --versioning-configuration Status=Enabled \
  && echo "✅ Enabled versioning on documents bucket"

aws s3api put-bucket-versioning \
  --bucket $S3_UPLOADS_BUCKET \
  --versioning-configuration Status=Enabled \
  && echo "✅ Enabled versioning on uploads bucket"

echo ""
echo "Step 4: Create DynamoDB Tables"
echo "-------------------------------"

# Chat Sessions Table
aws dynamodb create-table \
  --table-name smart-tutor-chat-sessions \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=session_id,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=session_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  2>/dev/null && echo "✅ Created chat sessions table" || echo "⚠️  Chat sessions table may already exist"

# Users Table
aws dynamodb create-table \
  --table-name smart-tutor-users \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  2>/dev/null && echo "✅ Created users table" || echo "⚠️  Users table may already exist"

# Quiz Results Table
aws dynamodb create-table \
  --table-name smart-tutor-quiz-results \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
    AttributeName=quiz_id,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
    AttributeName=quiz_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  2>/dev/null && echo "✅ Created quiz results table" || echo "⚠️  Quiz results table may already exist"

echo ""
echo "Step 5: Create CloudWatch Log Groups"
echo "-------------------------------------"

aws logs create-log-group \
  --log-group-name /aws/smart-ai-tutor/backend \
  --region $AWS_REGION \
  2>/dev/null && echo "✅ Created backend log group" || echo "⚠️  Backend log group may already exist"

aws logs create-log-group \
  --log-group-name /aws/smart-ai-tutor/cost-tracking \
  --region $AWS_REGION \
  2>/dev/null && echo "✅ Created cost tracking log group" || echo "⚠️  Cost tracking log group may already exist"

# Set retention to 30 days
aws logs put-retention-policy \
  --log-group-name /aws/smart-ai-tutor/backend \
  --retention-in-days 30 \
  --region $AWS_REGION \
  && echo "✅ Set backend log retention to 30 days"

aws logs put-retention-policy \
  --log-group-name /aws/smart-ai-tutor/cost-tracking \
  --retention-in-days 90 \
  --region $AWS_REGION \
  && echo "✅ Set cost log retention to 90 days"

echo ""
echo "Step 6: Update .env Configuration"
echo "----------------------------------"

cat >> .env << 'ENV_UPDATE'

# ===================================================================
# AWS Production Configuration (Updated)
# ===================================================================

# Storage Backend
STORAGE_BACKEND=dynamodb

# S3 Buckets
S3_LOGS_BUCKET=smart-ai-tutor-logs

# DynamoDB Tables
DYNAMODB_TABLE_USER_SESSIONS=smart-tutor-user-sessions

# CloudWatch Logs
CLOUDWATCH_LOG_GROUP=/aws/smart-ai-tutor/backend
CLOUDWATCH_ENABLED=true

ENV_UPDATE

echo "✅ Updated .env with AWS production settings"

echo ""
echo "=========================================="
echo "  AWS Setup Complete!"
echo "=========================================="
echo ""
echo "📊 Resources Created:"
echo "  - S3 Buckets:"
echo "    • $S3_DOCUMENTS_BUCKET (documents + vector index)"
echo "    • $S3_UPLOADS_BUCKET (user uploads)"
echo "    • $S3_LOGS_BUCKET (cost tracking + application logs)"
echo "  - DynamoDB Tables:"
echo "    • smart-tutor-chat-sessions"
echo "    • smart-tutor-users"
echo "    • smart-tutor-quiz-results"
echo "  - CloudWatch Log Groups:"
echo "    • /aws/smart-ai-tutor/backend"
echo "    • /aws/smart-ai-tutor/cost-tracking"
echo ""
echo "🎯 Next Steps:"
echo "1. Restart backend: ./manage_services.sh restart backend"
echo "2. Test in UI: http://localhost:3000"
echo "3. Monitor costs: Check S3: s3://$S3_LOGS_BUCKET/cost_tracking/"
echo "4. View logs: aws logs tail /aws/smart-ai-tutor/backend --follow"
echo ""
echo "💰 Estimated Monthly Costs:"
echo "  - DynamoDB (on-demand): ~\$5-25 (depending on usage)"
echo "  - S3 Storage: ~\$2-5"
echo "  - CloudWatch Logs: ~\$1-3"
echo "  - Bedrock (computed separately based on usage)"
echo "  Total (excluding Bedrock): ~\$8-33/month"
echo ""
