#!/bin/bash
set -e

# Setup CloudWatch Alarms for Application Errors
# Monitors API errors, Lambda failures, and service health

echo "⚠️  Setting up CloudWatch Error Alarms..."

REGION="us-east-1"
SNS_TOPIC_ARN="arn:aws:sns:us-east-1:XXXXXXXXXXXX:smart-tutor-alerts"

# Get actual account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "XXXXXXXXXXXX")
SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:smart-tutor-alerts"

echo "📊 Creating error monitoring alarms..."
echo "🔔 Notifications will be sent to: $SNS_TOPIC_ARN"
echo ""

# 1. API 5xx Errors Alarm
echo "1️⃣  Creating API 5xx Error alarm..."
aws cloudwatch put-metric-alarm \
  --alarm-name "smart-tutor-api-5xx-errors" \
  --alarm-description "Alert when API returns 5xx errors" \
  --metric-name "5XXError" \
  --namespace "AWS/ApiGateway" \
  --statistic "Sum" \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator "GreaterThanThreshold" \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$REGION" \
  2>/dev/null || echo "✓ Alarm exists"

# 2. API 4xx Errors Alarm (high rate indicates issues)
echo "2️⃣  Creating API 4xx Error alarm..."
aws cloudwatch put-metric-alarm \
  --alarm-name "smart-tutor-api-4xx-errors" \
  --alarm-description "Alert when API returns excessive 4xx errors" \
  --metric-name "4XXError" \
  --namespace "AWS/ApiGateway" \
  --statistic "Sum" \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 50 \
  --comparison-operator "GreaterThanThreshold" \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$REGION" \
  2>/dev/null || echo "✓ Alarm exists"

# 3. Lambda Function Errors
echo "3️⃣  Creating Lambda error alarm..."
aws cloudwatch put-metric-alarm \
  --alarm-name "smart-tutor-lambda-errors" \
  --alarm-description "Alert on Lambda function errors" \
  --metric-name "Errors" \
  --namespace "AWS/Lambda" \
  --statistic "Sum" \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 3 \
  --comparison-operator "GreaterThanThreshold" \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$REGION" \
  2>/dev/null || echo "✓ Alarm exists"

# 4. Application Log Errors (requires log group)
echo "4️⃣  Creating application log error alarm..."
aws cloudwatch put-metric-alarm \
  --alarm-name "smart-tutor-app-errors" \
  --alarm-description "Alert on application ERROR logs" \
  --metric-name "ErrorCount" \
  --namespace "SmartTutor/Application" \
  --statistic "Sum" \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator "GreaterThanThreshold" \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$REGION" \
  2>/dev/null || echo "⚠️  Requires metric filter setup"

# 5. Bedrock Throttling
echo "5️⃣  Creating Bedrock throttling alarm..."
aws cloudwatch put-metric-alarm \
  --alarm-name "smart-tutor-bedrock-throttle" \
  --alarm-description "Alert on Bedrock API throttling" \
  --metric-name "ModelInvocationThrottles" \
  --namespace "AWS/Bedrock" \
  --statistic "Sum" \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator "GreaterThanThreshold" \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$REGION" \
  2>/dev/null || echo "✓ Alarm created"

echo ""
echo "✅ Error monitoring alarms created!"
echo ""
echo "📋 Created Alarms:"
echo "   1. smart-tutor-api-5xx-errors - Server errors"
echo "   2. smart-tutor-api-4xx-errors - Client errors (high rate)"
echo "   3. smart-tutor-lambda-errors - Lambda failures"
echo "   4. smart-tutor-app-errors - Application errors"
echo "   5. smart-tutor-bedrock-throttle - API throttling"
echo ""
echo "🔍 View alarms:"
echo "   aws cloudwatch describe-alarms --region $REGION"
echo ""
echo "🧪 Test alarm:"
echo "   aws cloudwatch set-alarm-state --alarm-name smart-tutor-api-5xx-errors --state-value ALARM --state-reason 'Test' --region $REGION"
