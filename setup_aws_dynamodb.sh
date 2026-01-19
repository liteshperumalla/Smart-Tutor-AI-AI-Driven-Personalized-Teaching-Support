#!/bin/bash

# Setup AWS DynamoDB for Smart AI Tutor
# This script creates necessary DynamoDB tables and configures permissions

echo "=========================================="
echo "AWS DynamoDB Setup for Smart AI Tutor"
echo "=========================================="
echo ""

# Configuration
AWS_REGION="us-east-1"
TABLE_CHAT_SESSIONS="smart-tutor-chat-sessions"
TABLE_USERS="smart-tutor-users"
TABLE_QUIZ_RESULTS="smart-tutor-quiz-results"

echo "Step 1: Create IAM Policy for DynamoDB"
echo "--------------------------------------"
echo "You need to attach this policy to your IAM user:"
echo ""

cat > /tmp/dynamodb-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBTableAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:ListTables",
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:BatchGetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/smart-tutor-*"
      ]
    },
    {
      "Sid": "DynamoDBIndexAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/smart-tutor-*/index/*"
      ]
    }
  ]
}
EOF

cat /tmp/dynamodb-policy.json
echo ""
echo "To attach this policy to your IAM user, run:"
echo "  aws iam put-user-policy --user-name smart-tutor --policy-name DynamoDBAccess --policy-document file:///tmp/dynamodb-policy.json"
echo ""

echo "Step 2: Create DynamoDB Tables"
echo "-------------------------------"
echo "Creating chat sessions table..."

aws dynamodb create-table \
  --table-name $TABLE_CHAT_SESSIONS \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=session_id,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=session_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  2>/dev/null

if [ $? -eq 0 ]; then
  echo "✅ Chat sessions table created"
else
  echo "⚠️  Chat sessions table may already exist or permissions error"
fi

echo ""
echo "Creating users table..."

aws dynamodb create-table \
  --table-name $TABLE_USERS \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
  --global-secondary-indexes \
    IndexName=email-index,KeySchema=["{AttributeName=email,KeyType=HASH}"],Projection="{ProjectionType=ALL}" \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  2>/dev/null

if [ $? -eq 0 ]; then
  echo "✅ Users table created"
else
  echo "⚠️  Users table may already exist or permissions error"
fi

echo ""
echo "Creating quiz results table..."

aws dynamodb create-table \
  --table-name $TABLE_QUIZ_RESULTS \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
    AttributeName=quiz_id,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
    AttributeName=quiz_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production \
  2>/dev/null

if [ $? -eq 0 ]; then
  echo "✅ Quiz results table created"
else
  echo "⚠️  Quiz results table may already exist or permissions error"
fi

echo ""
echo "Step 3: Verify Tables"
echo "---------------------"
aws dynamodb list-tables --region $AWS_REGION 2>/dev/null | grep smart-tutor

echo ""
echo "=========================================="
echo "DynamoDB Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Verify tables in AWS Console: https://console.aws.amazon.com/dynamodbv2"
echo "2. Update .env: STORAGE_BACKEND=dynamodb"
echo "3. Restart backend services"
