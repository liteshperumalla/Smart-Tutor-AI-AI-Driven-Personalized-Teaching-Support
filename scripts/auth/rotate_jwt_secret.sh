#!/bin/bash
set -e

# Script to rotate JWT secret in AWS Secrets Manager
# This generates a new strong JWT secret and updates it in Secrets Manager

echo "🔄 Rotating JWT Secret in AWS Secrets Manager..."

# Configuration
SECRET_NAME="smart-tutor/app/secrets"
REGION="us-east-1"

# Generate a new strong JWT secret (64 character random string)
NEW_JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')

echo "✓ Generated new JWT secret"

# Get current secret value
echo "📥 Fetching current secret..."
CURRENT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --region "$REGION" \
  --query 'SecretString' \
  --output text 2>/dev/null || echo "{}")

# Parse and update the secret
echo "🔧 Updating JWT_SECRET_KEY..."

# Create updated secret JSON
UPDATED_SECRET=$(echo "$CURRENT_SECRET" | jq --arg jwt "$NEW_JWT_SECRET" '. + {JWT_SECRET_KEY: $jwt}')

# Update secret in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id "$SECRET_NAME" \
  --secret-string "$UPDATED_SECRET" \
  --region "$REGION" \
  --description "JWT secret rotated on $(date -u +%Y-%m-%d)" \
  > /dev/null

echo "✅ JWT secret successfully rotated in Secrets Manager"
echo "📝 Secret: $SECRET_NAME"
echo "🕐 Timestamp: $(date -u)"
echo ""
echo "⚠️  IMPORTANT: Restart all application services to pick up the new secret"
echo "   Run: ./manage_services.sh restart"
