#!/bin/bash
# Create S3 buckets for Smart AI Tutor

set -e  # Exit on error

echo "=================================="
echo "Creating S3 Buckets for Smart AI Tutor"
echo "=================================="
echo ""

# Configuration
REGION="us-east-1"
DOCS_BUCKET="smart-ai-tutor-docs"
UPLOADS_BUCKET="smart-ai-tutor-uploads"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first:"
    echo "   brew install awscli"
    exit 1
fi

echo "✓ AWS CLI found"
echo ""

# Create documents bucket
echo "1. Creating documents bucket: $DOCS_BUCKET"
if aws s3 mb "s3://$DOCS_BUCKET" --region "$REGION" 2>/dev/null; then
    echo "   ✓ Bucket created successfully"
else
    echo "   ⚠ Bucket may already exist or error occurred"
fi

# Create uploads bucket
echo ""
echo "2. Creating uploads bucket: $UPLOADS_BUCKET"
if aws s3 mb "s3://$UPLOADS_BUCKET" --region "$REGION" 2>/dev/null; then
    echo "   ✓ Bucket created successfully"
else
    echo "   ⚠ Bucket may already exist or error occurred"
fi

# Enable versioning on documents bucket
echo ""
echo "3. Enabling versioning on documents bucket..."
aws s3api put-bucket-versioning \
    --bucket "$DOCS_BUCKET" \
    --versioning-configuration Status=Enabled \
    2>/dev/null && echo "   ✓ Versioning enabled" || echo "   ⚠ Could not enable versioning"

# Set lifecycle policy (optional - delete old versions after 90 days)
echo ""
echo "4. Setting lifecycle policy..."
cat > /tmp/lifecycle.json << 'LIFECYCLE'
{
  "Rules": [
    {
      "Id": "DeleteOldVersions",
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 90
      }
    }
  ]
}
LIFECYCLE

aws s3api put-bucket-lifecycle-configuration \
    --bucket "$DOCS_BUCKET" \
    --lifecycle-configuration file:///tmp/lifecycle.json \
    2>/dev/null && echo "   ✓ Lifecycle policy set" || echo "   ⚠ Could not set lifecycle policy"

rm /tmp/lifecycle.json

echo ""
echo "=================================="
echo "✅ S3 Buckets Setup Complete!"
echo "=================================="
echo ""
echo "Buckets created:"
echo "  • s3://$DOCS_BUCKET (with versioning)"
echo "  • s3://$UPLOADS_BUCKET"
echo ""
echo "Next steps:"
echo "  1. Upload course materials:"
echo "     aws s3 sync ./Modules/ s3://$DOCS_BUCKET/modules/"
echo "     aws s3 sync ./data/ s3://$DOCS_BUCKET/data/"
echo ""
echo "  2. Verify buckets:"
echo "     aws s3 ls"
echo ""
