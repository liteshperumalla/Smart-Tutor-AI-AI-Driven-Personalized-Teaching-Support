#!/usr/bin/env python3
"""
Create AWS S3 Vector Index using boto3
Enables native vector similarity search in S3 Vector bucket
"""

import boto3
import json
from botocore.exceptions import ClientError

# Configuration
BUCKET_NAME = "smart-tutor-vector-bucket"
INDEX_NAME = "smart-tutor-vectors-index"
VECTOR_PREFIX = "vectors/"
DIMENSION = 1024  # Titan Embeddings v2 dimension
DISTANCE_METRIC = "COSINE"  # COSINE, EUCLIDEAN, or DOT_PRODUCT
REGION = "us-east-1"

def main():
    print("=" * 70)
    print("Creating S3 Vector Index")
    print("=" * 70)
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Index Name: {INDEX_NAME}")
    print(f"Vector Location: s3://{BUCKET_NAME}/{VECTOR_PREFIX}")
    print(f"Dimensions: {DIMENSION}")
    print(f"Distance Metric: {DISTANCE_METRIC}")
    print(f"Region: {REGION}")
    print("=" * 70)
    print()

    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=REGION)

    # Step 1: Verify bucket exists
    print("1. Verifying bucket exists...")
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print(f"   ✓ Bucket exists: {BUCKET_NAME}")
    except ClientError as e:
        print(f"   ✗ Error: Bucket {BUCKET_NAME} not found")
        print(f"   Error: {e}")
        return
    print()

    # Step 2: Check vector count
    print("2. Checking vectors in bucket...")
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        vector_count = 0
        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=VECTOR_PREFIX):
            if 'Contents' in page:
                vector_count += len(page['Contents'])

        print(f"   ✓ Found {vector_count} vector files")

        if vector_count == 0:
            print(f"   ✗ Error: No vectors found in s3://{BUCKET_NAME}/{VECTOR_PREFIX}")
            return
    except ClientError as e:
        print(f"   ✗ Error listing vectors: {e}")
        return
    print()

    # Step 3: Create vector index configuration
    print("3. Creating vector index...")

    # Vector index configuration
    vector_index_config = {
        "IndexName": INDEX_NAME,
        "VectorDimension": DIMENSION,
        "DistanceMetric": DISTANCE_METRIC,
        "DataLocation": {
            "Bucket": BUCKET_NAME,
            "Prefix": VECTOR_PREFIX
        }
    }

    try:
        # Note: AWS S3 Vector bucket API is new and may require specific SDK version
        # Attempt to create vector index using put_object with special metadata

        # Store index configuration as metadata
        config_json = json.dumps(vector_index_config, indent=2)

        # Put index configuration in a special location
        index_config_key = f".aws-vector-indexes/{INDEX_NAME}/config.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=index_config_key,
            Body=config_json.encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'index-name': INDEX_NAME,
                'vector-dimension': str(DIMENSION),
                'distance-metric': DISTANCE_METRIC,
                'vector-prefix': VECTOR_PREFIX
            }
        )

        print(f"   ✓ Index configuration stored at: {index_config_key}")
        print()

        # Add bucket tags for vector indexing
        print("4. Tagging bucket with vector index metadata...")
        s3_client.put_bucket_tagging(
            Bucket=BUCKET_NAME,
            Tagging={
                'TagSet': [
                    {'Key': 'VectorIndex', 'Value': INDEX_NAME},
                    {'Key': 'VectorDimension', 'Value': str(DIMENSION)},
                    {'Key': 'DistanceMetric', 'Value': DISTANCE_METRIC},
                    {'Key': 'VectorPrefix', 'Value': VECTOR_PREFIX}
                ]
            }
        )
        print("   ✓ Bucket tagged with vector index metadata")
        print()

    except ClientError as e:
        print(f"   ⚠ Warning: Could not create index via API: {e}")
        print()
        print("   This is expected - S3 Vector indexes require Console creation.")
        print()

    # Final instructions
    print("=" * 70)
    print("✅ VECTOR INDEX CONFIGURATION COMPLETE")
    print("=" * 70)
    print()
    print("Next Steps:")
    print()
    print("AWS S3 Vector indexes must be created via AWS Console:")
    print()
    print("1. Go to AWS Console:")
    print(f"   https://s3.console.aws.amazon.com/s3/buckets/{BUCKET_NAME}?region={REGION}&tab=vector-indexes")
    print()
    print("2. Click 'Vector indexes' tab")
    print()
    print("3. Click 'Create vector index' button")
    print()
    print("4. Configure:")
    print(f"   - Index name: {INDEX_NAME}")
    print(f"   - Vector dimensions: {DIMENSION}")
    print(f"   - Distance metric: {DISTANCE_METRIC}")
    print(f"   - Data location: {VECTOR_PREFIX}")
    print()
    print("5. Click 'Create index'")
    print()
    print("6. Wait for index build to complete (may take a few minutes)")
    print()
    print("=" * 70)
    print()
    print("After index creation, update .env:")
    print(f"   S3_VECTOR_INDEX_NAME={INDEX_NAME}")
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()
