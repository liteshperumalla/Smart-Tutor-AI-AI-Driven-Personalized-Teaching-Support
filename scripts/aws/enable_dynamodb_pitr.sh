#!/bin/bash
set -e

# Enable DynamoDB Point-in-Time Recovery (PITR) for all tables

echo "⏰ Enabling DynamoDB Point-in-Time Recovery..."

REGION="us-east-1"

# List of DynamoDB tables
TABLES=(
  "smart-tutor-users"
  "smart-tutor-sessions"
  "smart-tutor-messages"
  "smart-tutor-documents"
)

echo ""
echo "📊 Current PITR Status:"
echo ""

for TABLE in "${TABLES[@]}"; do
  echo "Checking $TABLE..."

  # Check if table exists
  if aws dynamodb describe-table \
    --table-name "$TABLE" \
    --region "$REGION" \
    &>/dev/null; then

    # Get PITR status
    PITR_STATUS=$(aws dynamodb describe-continuous-backups \
      --table-name "$TABLE" \
      --region "$REGION" \
      --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
      --output text 2>/dev/null || echo "DISABLED")

    if [ "$PITR_STATUS" == "ENABLED" ]; then
      echo "  ✅ PITR already enabled"
    else
      echo "  🔧 Enabling PITR..."
      aws dynamodb update-continuous-backups \
        --table-name "$TABLE" \
        --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
        --region "$REGION" \
        > /dev/null
      echo "  ✅ PITR enabled"
    fi
  else
    echo "  ⚠️  Table does not exist yet"
  fi
  echo ""
done

echo ""
echo "📋 PITR Summary:"
echo ""

for TABLE in "${TABLES[@]}"; do
  if aws dynamodb describe-table \
    --table-name "$TABLE" \
    --region "$REGION" \
    &>/dev/null; then

    aws dynamodb describe-continuous-backups \
      --table-name "$TABLE" \
      --region "$REGION" \
      --query '{
        Table:TableName,
        PITRStatus:ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus,
        EarliestRestoreTime:ContinuousBackupsDescription.PointInTimeRecoveryDescription.EarliestRestorableDateTime,
        LatestRestoreTime:ContinuousBackupsDescription.PointInTimeRecoveryDescription.LatestRestorableDateTime
      }' \
      --output table 2>/dev/null || echo "Table: $TABLE - Not found"
    echo ""
  fi
done

echo "✅ Point-in-Time Recovery configuration complete!"
echo ""
echo "📝 Notes:"
echo "   - PITR provides continuous backups for the last 35 days"
echo "   - No performance impact on tables"
echo "   - Additional cost: ~$0.20 per GB per month"
echo "   - Restore to any point in time within the 35-day window"
echo ""
echo "🔄 To restore a table:"
echo "   aws dynamodb restore-table-to-point-in-time \\"
echo "     --source-table-name TABLE_NAME \\"
echo "     --target-table-name TABLE_NAME-restored \\"
echo "     --restore-date-time 2025-12-19T00:00:00Z \\"
echo "     --region $REGION"
