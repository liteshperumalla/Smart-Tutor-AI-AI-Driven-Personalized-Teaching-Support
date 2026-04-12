#!/bin/bash

# Setup AWS RDS PostgreSQL for Smart AI Tutor
# This script guides you through creating RDS PostgreSQL

set -e

echo "=========================================="
echo "AWS RDS PostgreSQL Setup"
echo "=========================================="
echo ""

# Configuration
DB_INSTANCE_ID="smart-tutor-postgres"
DB_NAME="smart_tutor"
DB_USERNAME="smart_tutor_admin"
DB_PASSWORD="SmartTutor2025!SecurePass"  # CHANGE THIS IN PRODUCTION
DB_CLASS="db.t3.micro"
AWS_REGION="us-east-1"

echo "Configuration:"
echo "  Instance ID: $DB_INSTANCE_ID"
echo "  Database Name: $DB_NAME"
echo "  Username: $DB_USERNAME"
echo "  Password: $DB_PASSWORD (CHANGE IN PRODUCTION!)"
echo "  Instance Class: $DB_CLASS (Free tier eligible)"
echo "  Region: $AWS_REGION"
echo ""

echo "Step 1: Attach RDS IAM Policy"
echo "------------------------------"
echo "The IAM policy has been created at /tmp/rds-iam-policy.json"
echo ""
echo "Option A: AWS Console (Recommended)"
echo "  1. Go to: https://console.aws.amazon.com/iam/"
echo "  2. Users → smart-tutor → Add permissions"
echo "  3. Create inline policy → JSON tab"
echo "  4. Paste from /tmp/rds-iam-policy.json"
echo "  5. Policy name: SmartTutorRDSAccess"
echo "  6. Create policy"
echo ""
echo "Option B: AWS CLI (if you have admin access)"
echo "  aws iam put-user-policy \\"
echo "    --user-name smart-tutor \\"
echo "    --policy-name SmartTutorRDSAccess \\"
echo "    --policy-document file:///tmp/rds-iam-policy.json"
echo ""
read -p "Press Enter after attaching the policy..."

echo ""
echo "Step 2: Create RDS PostgreSQL Instance"
echo "---------------------------------------"
echo ""
echo "Creating RDS instance... (This takes 5-10 minutes)"
echo ""

# Try to create RDS instance
aws rds create-db-instance \
  --db-instance-identifier $DB_INSTANCE_ID \
  --db-name $DB_NAME \
  --master-username $DB_USERNAME \
  --master-user-password $DB_PASSWORD \
  --db-instance-class $DB_CLASS \
  --engine postgres \
  --engine-version 15.4 \
  --allocated-storage 20 \
  --storage-type gp2 \
  --storage-encrypted \
  --publicly-accessible \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "mon:04:00-mon:05:00" \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  --region $AWS_REGION \
  2>&1

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ RDS Instance creation initiated!"
  echo ""
else
  echo ""
  echo "⚠️  If instance already exists, that's OK. Continuing..."
  echo ""
fi

echo "Step 3: Wait for Instance to become Available"
echo "----------------------------------------------"
echo ""
echo "Waiting for RDS instance to become available..."
echo "(This can take 5-10 minutes)"
echo ""

# Wait for instance to be available
aws rds wait db-instance-available \
  --db-instance-identifier $DB_INSTANCE_ID \
  --region $AWS_REGION \
  2>&1 || echo "Waiting..."

echo ""
echo "Step 4: Get Instance Endpoint"
echo "------------------------------"
echo ""

# Get instance details
INSTANCE_INFO=$(aws rds describe-db-instances \
  --db-instance-identifier $DB_INSTANCE_ID \
  --region $AWS_REGION \
  --query 'DBInstances[0]' \
  2>/dev/null)

if [ $? -eq 0 ]; then
  ENDPOINT=$(echo $INSTANCE_INFO | jq -r '.Endpoint.Address')
  PORT=$(echo $INSTANCE_INFO | jq -r '.Endpoint.Port')
  STATUS=$(echo $INSTANCE_INFO | jq -r '.DBInstanceStatus')

  echo "✅ RDS Instance Details:"
  echo "  Status: $STATUS"
  echo "  Endpoint: $ENDPOINT"
  echo "  Port: $PORT"
  echo "  Database: $DB_NAME"
  echo "  Username: $DB_USERNAME"
  echo ""

  if [ "$STATUS" = "available" ]; then
    echo "✅ Instance is READY!"
    echo ""

    echo "Step 5: Configure Security Group"
    echo "---------------------------------"
    echo ""
    echo "To allow connections from your IP:"
    echo ""
    echo "1. Go to: https://console.aws.amazon.com/rds/"
    echo "2. Click on: $DB_INSTANCE_ID"
    echo "3. Click on the VPC security group"
    echo "4. Edit inbound rules"
    echo "5. Add rule: PostgreSQL (port 5432) from your IP"
    echo "   (Get your IP: curl ifconfig.me)"
    echo ""
    read -p "Press Enter after configuring security group..."

    echo ""
    echo "Step 6: Update .env Configuration"
    echo "----------------------------------"
    echo ""
    echo "Add these lines to your .env file:"
    echo ""
    echo "# PostgreSQL (AWS RDS)"
    echo "STORAGE_BACKEND=hybrid"
    echo "POSTGRES_HOST=$ENDPOINT"
    echo "POSTGRES_PORT=$PORT"
    echo "POSTGRES_DB=$DB_NAME"
    echo "POSTGRES_USER=$DB_USERNAME"
    echo "POSTGRES_PASSWORD=$DB_PASSWORD"
    echo ""

    # Optionally update .env automatically
    read -p "Update .env automatically? (y/n): " UPDATE_ENV
    if [ "$UPDATE_ENV" = "y" ]; then
      # Backup .env
      cp .env .env.backup

      # Update .env
      sed -i.bak "s/^STORAGE_BACKEND=.*/STORAGE_BACKEND=hybrid/" .env
      sed -i.bak "s/^POSTGRES_HOST=.*/POSTGRES_HOST=$ENDPOINT/" .env
      sed -i.bak "s/^POSTGRES_PORT=.*/POSTGRES_PORT=$PORT/" .env
      sed -i.bak "s/^POSTGRES_DB=.*/POSTGRES_DB=$DB_NAME/" .env
      sed -i.bak "s/^POSTGRES_USER=.*/POSTGRES_USER=$DB_USERNAME/" .env
      sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$DB_PASSWORD/" .env

      echo "✅ .env updated (backup saved as .env.backup)"
    fi

    echo ""
    echo "Step 7: Initialize Database Schema"
    echo "-----------------------------------"
    echo ""
    echo "Run this to create tables:"
    echo "  source venv/bin/activate"
    echo "  alembic -c alembic.ini upgrade head"
    echo ""

    echo ""
    echo "=========================================="
    echo "✅ RDS PostgreSQL Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Connection String:"
    echo "  postgresql://$DB_USERNAME:$DB_PASSWORD@$ENDPOINT:$PORT/$DB_NAME"
    echo ""
    echo "Next steps:"
    echo "  1. Configure security group (allow your IP)"
    echo "  2. Initialize database schema"
    echo "  3. Restart backend: ./manage_services.sh restart backend"
    echo "  4. Test hybrid storage"
    echo ""
    echo "Estimated Monthly Cost:"
    echo "  db.t3.micro: ~\$15-20/month"
    echo "  20 GB storage: ~\$2/month"
    echo "  Backups: ~\$2/month"
    echo "  Total: ~\$19-24/month"
    echo ""
  else
    echo "⚠️  Instance status: $STATUS"
    echo "   Wait for it to become 'available' and re-run this script"
  fi
else
  echo "❌ Could not get instance details"
  echo "   Check if instance exists:"
  echo "   aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID"
fi

echo ""
echo "=========================================="
