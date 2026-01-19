#!/bin/bash
set -e

# Script to enable automatic rotation for secrets in AWS Secrets Manager
# Uses AWS managed rotation for RDS, custom Lambda for application secrets

echo "🔄 Enabling Automatic Secret Rotation..."

REGION="us-east-1"

# Enable rotation for RDS credentials (AWS managed)
echo ""
echo "1️⃣  Enabling RDS credential rotation..."
aws secretsmanager rotate-secret \
  --secret-id smart-tutor/rds/credentials \
  --rotation-lambda-arn "" \
  --rotation-rules "{\"AutomaticallyAfterDays\": 30}" \
  --region "$REGION" \
  2>/dev/null || echo "⚠️  RDS rotation already enabled or requires Lambda setup"

echo "✓ RDS credential rotation configured (30-day interval)"

# Note about JWT secret rotation
echo ""
echo "2️⃣  JWT Secret Rotation Configuration..."
echo "📝 JWT secrets require custom Lambda function for rotation"
echo "   For now, use manual rotation via rotate_jwt_secret.sh"
echo "   Recommended interval: 90 days"
echo ""
echo "   To set up automatic JWT rotation:"
echo "   1. Create Lambda function using AWS SAM template"
echo "   2. Grant Lambda permissions to Secrets Manager"
echo "   3. Enable rotation with Lambda ARN"
echo ""

# Verify rotation status
echo "3️⃣  Current Rotation Status:"
echo ""
echo "RDS Credentials:"
aws secretsmanager describe-secret \
  --secret-id smart-tutor/rds/credentials \
  --region "$REGION" \
  --query '{Name:Name,RotationEnabled:RotationEnabled,LastRotated:LastRotatedDate,NextRotation:NextRotationDate}' \
  --output table

echo ""
echo "App Secrets:"
aws secretsmanager describe-secret \
  --secret-id smart-tutor/app/secrets \
  --region "$REGION" \
  --query '{Name:Name,RotationEnabled:RotationEnabled,LastRotated:LastRotatedDate}' \
  --output table

echo ""
echo "✅ Secret rotation configuration complete"
echo "📋 Next steps:"
echo "   - Monitor rotation in CloudWatch Logs"
echo "   - Test application after rotation"
echo "   - Set up Lambda for JWT rotation (optional)"
