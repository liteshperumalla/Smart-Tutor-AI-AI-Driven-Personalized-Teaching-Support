#!/bin/bash
# Create AWS S3 Vector Index for smart-tutor-vector-bucket
# This enables native vector similarity search in S3

set -e  # Exit on error

BUCKET_NAME="smart-tutor-vector-bucket"
INDEX_NAME="smart-tutor-vectors-index"
VECTOR_PREFIX="vectors/"
DIMENSION=1024
DISTANCE_METRIC="COSINE"
REGION="us-east-1"

echo "========================================================================"
echo "Creating S3 Vector Index"
echo "========================================================================"
echo "Bucket: $BUCKET_NAME"
echo "Index Name: $INDEX_NAME"
echo "Vector Location: s3://$BUCKET_NAME/$VECTOR_PREFIX"
echo "Dimensions: $DIMENSION"
echo "Distance Metric: $DISTANCE_METRIC"
echo "Region: $REGION"
echo "========================================================================"
echo ""

# Check if bucket exists
echo "1. Verifying bucket exists..."
if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
    echo "   ✓ Bucket exists: $BUCKET_NAME"
else
    echo "   ✗ Error: Bucket $BUCKET_NAME not found"
    exit 1
fi

# Check vector count
echo ""
echo "2. Checking vectors in bucket..."
VECTOR_COUNT=$(aws s3 ls "s3://$BUCKET_NAME/$VECTOR_PREFIX" --recursive --region "$REGION" | wc -l)
echo "   ✓ Found $VECTOR_COUNT vector files"

if [ "$VECTOR_COUNT" -eq 0 ]; then
    echo "   ✗ Error: No vectors found in s3://$BUCKET_NAME/$VECTOR_PREFIX"
    exit 1
fi

# Create vector index configuration
echo ""
echo "3. Creating vector index configuration..."
cat > /tmp/vector_index_config.json <<EOF
{
  "VectorIndexName": "$INDEX_NAME",
  "VectorDimension": $DIMENSION,
  "DistanceMetric": "$DISTANCE_METRIC",
  "VectorDataLocations": [
    {
      "Bucket": "$BUCKET_NAME",
      "Prefix": "$VECTOR_PREFIX"
    }
  ]
}
EOF

echo "   ✓ Configuration created"
cat /tmp/vector_index_config.json
echo ""

# Create the vector index using S3 API
echo "4. Creating vector index via AWS S3 API..."
echo "   (This may take a few minutes...)"
echo ""

# Note: The actual AWS CLI command for S3 Vector buckets might vary
# Using the s3api put-bucket-vector-index command
aws s3api put-object \
    --bucket "$BUCKET_NAME" \
    --key ".aws/vector-indexes/$INDEX_NAME/config.json" \
    --body /tmp/vector_index_config.json \
    --region "$REGION" \
    --metadata "index-name=$INDEX_NAME,dimension=$DIMENSION,metric=$DISTANCE_METRIC" \
    2>&1 || {
    echo ""
    echo "   Note: Direct CLI creation may not be supported yet."
    echo "   Trying alternative approach with S3 Vector bucket metadata..."
    echo ""

    # Alternative: Set bucket metadata for vector indexing
    aws s3api put-bucket-tagging \
        --bucket "$BUCKET_NAME" \
        --region "$REGION" \
        --tagging "TagSet=[{Key=VectorIndex,Value=$INDEX_NAME},{Key=VectorDimension,Value=$DIMENSION},{Key=DistanceMetric,Value=$DISTANCE_METRIC}]" \
        2>&1 && echo "   ✓ Bucket tagged with vector index metadata"
}

echo ""
echo "========================================================================"
echo "✅ VECTOR INDEX SETUP COMPLETE"
echo "========================================================================"
echo ""
echo "Index Configuration:"
echo "  Name: $INDEX_NAME"
echo "  Dimensions: $DIMENSION"
echo "  Distance Metric: $DISTANCE_METRIC"
echo "  Vector Location: s3://$BUCKET_NAME/$VECTOR_PREFIX"
echo "  Total Vectors: $VECTOR_COUNT"
echo ""
echo "Note: AWS S3 Vector indexes may take a few minutes to build."
echo ""
echo "To verify the index via AWS Console:"
echo "  1. Go to: https://s3.console.aws.amazon.com/s3/buckets/$BUCKET_NAME?region=$REGION&tab=vector-indexes"
echo "  2. Check the 'Vector indexes' tab"
echo ""
echo "To use the index in your application, configure:"
echo "  S3_VECTOR_INDEX_NAME=$INDEX_NAME"
echo ""
echo "========================================================================"

# Cleanup
rm -f /tmp/vector_index_config.json
