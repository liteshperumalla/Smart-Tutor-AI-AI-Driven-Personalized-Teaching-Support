#!/bin/bash
set -e

# Script to add Google OAuth credentials to AWS Secrets Manager

echo "🔐 Adding Google OAuth Credentials to AWS Secrets Manager"
echo "========================================================="
echo ""

SECRET_NAME="smart-tutor/app/secrets"
REGION="us-east-1"

# Get Client ID and Secret from user
echo "📝 You need to provide your Google OAuth credentials."
echo "   Get these from: https://console.cloud.google.com/apis/credentials"
echo ""

read -p "Enter Google OAuth Client ID: " CLIENT_ID
read -sp "Enter Google OAuth Client Secret: " CLIENT_SECRET
echo ""
echo ""

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  echo "❌ Both Client ID and Client Secret are required"
  exit 1
fi

# Get current secret value
echo "📥 Fetching current secrets..."
CURRENT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --region "$REGION" \
  --query 'SecretString' \
  --output text 2>/dev/null || echo "{}")

# Add Google OAuth credentials
echo "🔧 Adding Google OAuth credentials..."
UPDATED_SECRET=$(echo "$CURRENT_SECRET" | jq \
  --arg client_id "$CLIENT_ID" \
  --arg client_secret "$CLIENT_SECRET" \
  '. + {google_oauth_client_id: $client_id, google_oauth_client_secret: $client_secret}')

# Update secret in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id "$SECRET_NAME" \
  --secret-string "$UPDATED_SECRET" \
  --region "$REGION" \
  --description "Added Google OAuth credentials on $(date -u +%Y-%m-%d)" \
  > /dev/null

echo "✅ Google OAuth credentials added to Secrets Manager!"
echo ""
echo "📋 Current secrets in $SECRET_NAME:"
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --region "$REGION" \
  --query 'SecretString' \
  --output text | jq 'keys'

echo ""
echo "✅ Next steps:"
echo "   1. Update backend/config.py to load Google OAuth from Secrets Manager"
echo "   2. Restart backend service: ./manage_services.sh restart backend"
echo "   3. Test Google OAuth login"
