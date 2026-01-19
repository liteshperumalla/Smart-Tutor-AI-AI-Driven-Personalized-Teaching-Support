#!/bin/bash
set -e

# Verify and configure RDS automated backups

echo "💾 Verifying RDS Automated Backups..."

REGION="us-east-1"
DB_INSTANCE="smart-tutor-postgres"

echo ""
echo "📊 Current RDS Backup Configuration:"
echo ""

# Get RDS instance backup configuration
aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE" \
  --region "$REGION" \
  --query 'DBInstances[0].{
    Instance:DBInstanceIdentifier,
    BackupRetention:BackupRetentionPeriod,
    BackupWindow:PreferredBackupWindow,
    MaintenanceWindow:PreferredMaintenanceWindow,
    AutoMinorUpgrade:AutoMinorVersionUpgrade,
    MultiAZ:MultiAZ,
    StorageEncrypted:StorageEncrypted,
    LatestBackup:LatestRestorableTime
  }' \
  --output table

echo ""
echo "📦 Available Automated Backups:"
aws rds describe-db-snapshots \
  --db-instance-identifier "$DB_INSTANCE" \
  --snapshot-type automated \
  --region "$REGION" \
  --query 'DBSnapshots[*].{
    Snapshot:DBSnapshotIdentifier,
    Created:SnapshotCreateTime,
    Status:Status,
    Size:AllocatedStorage
  }' \
  --output table

echo ""
echo "🔍 Backup Analysis:"

# Get backup retention period
RETENTION=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE" \
  --region "$REGION" \
  --query 'DBInstances[0].BackupRetentionPeriod' \
  --output text)

if [ "$RETENTION" -eq 0 ]; then
  echo "❌ Automated backups are DISABLED"
  echo ""
  echo "🔧 Enable backups with:"
  echo "   aws rds modify-db-instance \\"
  echo "     --db-instance-identifier $DB_INSTANCE \\"
  echo "     --backup-retention-period 7 \\"
  echo "     --preferred-backup-window '03:00-04:00' \\"
  echo "     --apply-immediately \\"
  echo "     --region $REGION"
elif [ "$RETENTION" -lt 7 ]; then
  echo "⚠️  Backup retention is only $RETENTION days (recommended: 7-30 days)"
  echo ""
  echo "🔧 Increase retention with:"
  echo "   aws rds modify-db-instance \\"
  echo "     --db-instance-identifier $DB_INSTANCE \\"
  echo "     --backup-retention-period 30 \\"
  echo "     --apply-immediately \\"
  echo "     --region $REGION"
else
  echo "✅ Automated backups are enabled ($RETENTION day retention)"
fi

# Check encryption
ENCRYPTED=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE" \
  --region "$REGION" \
  --query 'DBInstances[0].StorageEncrypted' \
  --output text)

if [ "$ENCRYPTED" == "True" ]; then
  echo "✅ Storage encryption is enabled"
else
  echo "⚠️  Storage encryption is not enabled (requires new instance)"
fi

# Check Multi-AZ
MULTI_AZ=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE" \
  --region "$REGION" \
  --query 'DBInstances[0].MultiAZ' \
  --output text)

if [ "$MULTI_AZ" == "True" ]; then
  echo "✅ Multi-AZ deployment is enabled"
else
  echo "⚠️  Multi-AZ is not enabled (recommended for production)"
fi

echo ""
echo "📝 Recommendations:"
echo "   ✓ Backup retention: 30 days minimum"
echo "   ✓ Backup window: During low-traffic hours (e.g., 03:00-04:00 UTC)"
echo "   ✓ Multi-AZ: Enable for high availability"
echo "   ✓ Encryption: Enable for new instances"
echo ""
echo "🧪 Test restore procedure regularly!"
