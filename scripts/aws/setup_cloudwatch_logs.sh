#!/bin/bash
set -e

# Setup CloudWatch Logs for application monitoring

echo "📝 Setting up CloudWatch Logs Collection..."

REGION="us-east-1"
LOG_GROUP_PREFIX="/aws/smart-tutor"

echo ""
echo "Creating log groups..."

# 1. Application logs
echo "1️⃣  Creating application log group..."
aws logs create-log-group \
  --log-group-name "${LOG_GROUP_PREFIX}/application" \
  --region "$REGION" \
  2>/dev/null || echo "  ✓ Log group exists"

# Set retention to 30 days
aws logs put-retention-policy \
  --log-group-name "${LOG_GROUP_PREFIX}/application" \
  --retention-in-days 30 \
  --region "$REGION"
echo "  ✓ Retention: 30 days"

# 2. API Gateway logs
echo "2️⃣  Creating API Gateway log group..."
aws logs create-log-group \
  --log-group-name "${LOG_GROUP_PREFIX}/api-gateway" \
  --region "$REGION" \
  2>/dev/null || echo "  ✓ Log group exists"

aws logs put-retention-policy \
  --log-group-name "${LOG_GROUP_PREFIX}/api-gateway" \
  --retention-in-days 14 \
  --region "$REGION"
echo "  ✓ Retention: 14 days"

# 3. Backend service logs
echo "3️⃣  Creating backend service log group..."
aws logs create-log-group \
  --log-group-name "${LOG_GROUP_PREFIX}/backend" \
  --region "$REGION" \
  2>/dev/null || echo "  ✓ Log group exists"

aws logs put-retention-policy \
  --log-group-name "${LOG_GROUP_PREFIX}/backend" \
  --retention-in-days 30 \
  --region "$REGION"
echo "  ✓ Retention: 30 days"

# 4. Error logs (separate for quick access)
echo "4️⃣  Creating error log group..."
aws logs create-log-group \
  --log-group-name "${LOG_GROUP_PREFIX}/errors" \
  --region "$REGION" \
  2>/dev/null || echo "  ✓ Log group exists"

aws logs put-retention-policy \
  --log-group-name "${LOG_GROUP_PREFIX}/errors" \
  --retention-in-days 90 \
  --region "$REGION"
echo "  ✓ Retention: 90 days"

echo ""
echo "📊 Creating metric filters for error detection..."

# Create metric filter for ERROR level logs
echo "Creating ERROR metric filter..."
aws logs put-metric-filter \
  --log-group-name "${LOG_GROUP_PREFIX}/application" \
  --filter-name "ErrorCount" \
  --filter-pattern "[time, request_id, level = ERROR, ...]" \
  --metric-transformations \
    metricName=ErrorCount,metricNamespace=SmartTutor/Application,metricValue=1,defaultValue=0 \
  --region "$REGION" \
  2>/dev/null || echo "  ✓ Metric filter exists"

# Create metric filter for CRITICAL level logs
echo "Creating CRITICAL metric filter..."
aws logs put-metric-filter \
  --log-group-name "${LOG_GROUP_PREFIX}/application" \
  --filter-name "CriticalCount" \
  --filter-pattern "[time, request_id, level = CRITICAL, ...]" \
  --metric-transformations \
    metricName=CriticalCount,metricNamespace=SmartTutor/Application,metricValue=1,defaultValue=0 \
  --region "$REGION" \
  2>/dev/null || echo "  ✓ Metric filter exists"

echo ""
echo "✅ CloudWatch Logs setup complete!"
echo ""
echo "📋 Created Log Groups:"
echo "   ${LOG_GROUP_PREFIX}/application (30 days retention)"
echo "   ${LOG_GROUP_PREFIX}/api-gateway (14 days retention)"
echo "   ${LOG_GROUP_PREFIX}/backend (30 days retention)"
echo "   ${LOG_GROUP_PREFIX}/errors (90 days retention)"
echo ""
echo "📊 Metric Filters:"
echo "   ErrorCount - Counts ERROR level logs"
echo "   CriticalCount - Counts CRITICAL level logs"
echo ""
echo "🔍 View logs:"
echo "   aws logs tail ${LOG_GROUP_PREFIX}/application --follow --region $REGION"
echo ""
echo "📝 Next steps:"
echo "   1. Update application logger to send logs to CloudWatch"
echo "   2. Add structured logging (JSON format recommended)"
echo "   3. Configure log streaming from containers/EC2"
echo ""
echo "Example Python logging config:"
echo "---"
cat <<'EOF'
import boto3
import watchtower
import logging

logger = logging.getLogger(__name__)
handler = watchtower.CloudWatchLogHandler(
    log_group='/aws/smart-tutor/application',
    stream_name='backend-api'
)
logger.addHandler(handler)
EOF
