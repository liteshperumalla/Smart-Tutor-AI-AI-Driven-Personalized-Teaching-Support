#!/bin/bash

# Setup CloudWatch Alarms for Smart AI Tutor
# Monitors critical AWS services

set -e

AWS_REGION="us-east-1"
SNS_TOPIC_NAME="smart-tutor-alerts"
EMAIL="liteshperumalla@gmail.com"

echo "=========================================="
echo "CloudWatch Alarms Setup"
echo "=========================================="
echo ""

# Step 1: Create SNS Topic for Notifications
echo "Step 1: Creating SNS Topic for Alerts"
echo "------------------------------------------"
SNS_TOPIC_ARN=$(aws sns create-topic \
  --name $SNS_TOPIC_NAME \
  --region $AWS_REGION \
  --output text --query 'TopicArn' 2>/dev/null || \
  aws sns list-topics --region $AWS_REGION --output text --query "Topics[?contains(TopicArn, '$SNS_TOPIC_NAME')].TopicArn | [0]")

echo "✅ SNS Topic: $SNS_TOPIC_ARN"
echo ""

# Step 2: Subscribe email to SNS topic
echo "Step 2: Subscribing Email to Alerts"
echo "------------------------------------------"
aws sns subscribe \
  --topic-arn $SNS_TOPIC_ARN \
  --protocol email \
  --notification-endpoint $EMAIL \
  --region $AWS_REGION 2>/dev/null || echo "Email already subscribed or pending confirmation"

echo "⚠️  Check your email ($EMAIL) to confirm the subscription"
echo ""

# Step 3: Create RDS CPU Utilization Alarm
echo "Step 3: Creating RDS CPU Alarm"
echo "------------------------------------------"
aws cloudwatch put-metric-alarm \
  --alarm-name smart-tutor-rds-high-cpu \
  --alarm-description "RDS CPU utilization is above 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --datapoints-to-alarm 2 \
  --dimensions Name=DBInstanceIdentifier,Value=smart-tutor-postgres \
  --alarm-actions $SNS_TOPIC_ARN \
  --region $AWS_REGION

echo "✅ RDS CPU alarm created"
echo ""

# Step 4: Create RDS Connection Alarm
echo "Step 4: Creating RDS Connection Alarm"
echo "------------------------------------------"
aws cloudwatch put-metric-alarm \
  --alarm-name smart-tutor-rds-high-connections \
  --alarm-description "RDS database connections are high" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=DBInstanceIdentifier,Value=smart-tutor-postgres \
  --alarm-actions $SNS_TOPIC_ARN \
  --region $AWS_REGION

echo "✅ RDS Connection alarm created"
echo ""

# Step 5: Create DynamoDB Read Throttle Alarm
echo "Step 5: Creating DynamoDB Read Throttle Alarm"
echo "------------------------------------------"
aws cloudwatch put-metric-alarm \
  --alarm-name smart-tutor-dynamodb-read-throttle \
  --alarm-description "DynamoDB read requests are being throttled" \
  --metric-name ReadThrottleEvents \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=TableName,Value=smart-tutor-chat-sessions \
  --alarm-actions $SNS_TOPIC_ARN \
  --region $AWS_REGION

echo "✅ DynamoDB Read Throttle alarm created"
echo ""

# Step 6: Create DynamoDB Write Throttle Alarm
echo "Step 6: Creating DynamoDB Write Throttle Alarm"
echo "------------------------------------------"
aws cloudwatch put-metric-alarm \
  --alarm-name smart-tutor-dynamodb-write-throttle \
  --alarm-description "DynamoDB write requests are being throttled" \
  --metric-name WriteThrottleEvents \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=TableName,Value=smart-tutor-chat-sessions \
  --alarm-actions $SNS_TOPIC_ARN \
  --region $AWS_REGION

echo "✅ DynamoDB Write Throttle alarm created"
echo ""

# Step 7: Create Bedrock Model Invocation Error Alarm
echo "Step 7: Creating Bedrock Error Alarm"
echo "------------------------------------------"
aws cloudwatch put-metric-alarm \
  --alarm-name smart-tutor-bedrock-errors \
  --alarm-description "Bedrock model invocation errors detected" \
  --metric-name ModelInvocationClientErrors \
  --namespace AWS/Bedrock \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=ModelId,Value=meta.llama3-70b-instruct-v1:0 \
  --alarm-actions $SNS_TOPIC_ARN \
  --region $AWS_REGION 2>/dev/null || echo "Note: Bedrock metrics may not be available immediately"

echo "✅ Bedrock Error alarm created (if supported)"
echo ""

echo "=========================================="
echo "✅ CloudWatch Alarms Setup Complete!"
echo "=========================================="
echo ""
echo "Created Alarms:"
echo "  1. RDS High CPU (>80% for 10 minutes)"
echo "  2. RDS High Connections (>50 connections)"
echo "  3. DynamoDB Read Throttle (>10 events)"
echo "  4. DynamoDB Write Throttle (>10 events)"
echo "  5. Bedrock Model Errors (>5 errors)"
echo ""
echo "SNS Topic: $SNS_TOPIC_ARN"
echo "Email: $EMAIL"
echo ""
echo "⚠️  IMPORTANT: Check your email and confirm the SNS subscription!"
echo ""
echo "To view alarms:"
echo "  aws cloudwatch describe-alarms --region $AWS_REGION"
echo ""
echo "To test an alarm:"
echo "  aws cloudwatch set-alarm-state \\"
echo "    --alarm-name smart-tutor-rds-high-cpu \\"
echo "    --state-value ALARM \\"
echo "    --state-reason 'Testing alarm' \\"
echo "    --region $AWS_REGION"
echo ""
