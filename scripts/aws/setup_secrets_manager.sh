#!/bin/bash

# Setup AWS Secrets Manager for Smart AI Tutor
# Securely store RDS credentials and application secrets

set -e

echo "=========================================="
echo "AWS Secrets Manager Setup"
echo "=========================================="
echo ""

AWS_REGION="us-east-1"

echo "Step 1: Grant Secrets Manager IAM Permissions"
echo "----------------------------------------------"
echo ""
echo "IAM Policy needed (attach to smart-tutor user):"
echo ""

cat > /tmp/secrets-manager-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:DescribeSecret",
        "secretsmanager:ListSecrets",
        "secretsmanager:UpdateSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:183631304219:secret:smart-tutor/*"
      ]
    }
  ]
}
EOF

cat /tmp/secrets-manager-policy.json

echo ""
echo "To attach this policy:"
echo ""
echo "AWS Console:"
echo "  1. Go to IAM → Users → smart-tutor"
echo "  2. Add permissions → Create inline policy"
echo "  3. Paste JSON from /tmp/secrets-manager-policy.json"
echo "  4. Policy name: SmartTutorSecretsManagerAccess"
echo ""
echo "AWS CLI:"
echo "  aws iam put-user-policy \\"
echo "    --user-name smart-tutor \\"
echo "    --policy-name SmartTutorSecretsManagerAccess \\"
echo "    --policy-document file:///tmp/secrets-manager-policy.json"
echo ""
read -p "Press Enter after attaching the policy..."

echo ""
echo "Step 2: Create Secrets in Secrets Manager"
echo "------------------------------------------"
echo ""

# Create RDS credentials secret
echo "Creating RDS credentials secret..."
aws secretsmanager create-secret \
  --name smart-tutor/rds/credentials \
  --description "Smart AI Tutor RDS PostgreSQL credentials" \
  --secret-string '{
    "username": "smart_tutor_admin",
    "password": "SmartTutor2025!SecurePass",
    "host": "smart-tutor-postgres.cmfouoe8c2p1.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "database": "smart_tutor",
    "engine": "postgres"
  }' \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  --region $AWS_REGION \
  2>/dev/null || echo "⚠️  Secret may already exist"

echo "✅ RDS credentials secret created"

# Create application secrets
# REQUIRED: Set these environment variables before running this script.
# Do NOT commit real values; rotate any key that was previously hardcoded here.
: "${SMART_TUTOR_JWT_SECRET:?Set SMART_TUTOR_JWT_SECRET (min 64 random chars)}"
: "${SERPAPI_API_KEY:?Set SERPAPI_API_KEY from https://serpapi.com/manage-api-key}"
: "${LANGFUSE_PUBLIC_KEY:?Set LANGFUSE_PUBLIC_KEY from your Langfuse project settings}"
: "${LANGFUSE_SECRET_KEY:?Set LANGFUSE_SECRET_KEY from your Langfuse project settings}"

echo ""
echo "Creating application secrets..."
aws secretsmanager create-secret \
  --name smart-tutor/app/secrets \
  --description "Smart AI Tutor application API keys and secrets" \
  --secret-string "{\n    \"jwt_secret_key\": \"${SMART_TUTOR_JWT_SECRET}\",\n    \"serpapi_api_key\": \"${SERPAPI_API_KEY}\",\n    \"langfuse_public_key\": \"${LANGFUSE_PUBLIC_KEY}\",\n    \"langfuse_secret_key\": \"${LANGFUSE_SECRET_KEY}\"\n  }" \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  --region $AWS_REGION \
  2>/dev/null || echo "⚠️  Secret may already exist"

echo "✅ Application secrets created"

echo ""
echo "Step 3: Verify Secrets"
echo "----------------------"
echo ""

aws secretsmanager list-secrets \
  --filters Key=name,Values=smart-tutor/ \
  --region $AWS_REGION \
  --query 'SecretList[*].[Name,Description]' \
  --output table

echo ""
echo "=========================================="
echo "✅ Secrets Manager Setup Complete!"
echo "=========================================="
echo ""
echo "Secrets created:"
echo "  • smart-tutor/rds/credentials"
echo "  • smart-tutor/app/secrets"
echo ""
echo "Monthly Cost:"
echo "  • $0.40 per secret per month"
echo "  • $0.05 per 10,000 API calls"
echo "  • Total: ~$1/month for 2 secrets"
echo ""
echo "Next steps:"
echo "  1. Update backend to fetch from Secrets Manager"
echo "  2. Remove sensitive data from .env"
echo "  3. Test application"
echo ""
