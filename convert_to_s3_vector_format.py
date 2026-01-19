#!/usr/bin/env python3
"""
Convert JSON vectors to AWS S3 Vector bucket format (Parquet)
AWS S3 Vector indexes require Parquet files with specific schema
"""

import boto3
import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
import os

BUCKET_NAME = "smart-tutor-vector-bucket"
REGION = "us-east-1"
SOURCE_PREFIX = "vectors/"
TARGET_PREFIX = "vectors-parquet/"

print("=" * 70)
print("Converting Vectors to AWS S3 Vector Bucket Format")
print("=" * 70)
print(f"Source: s3://{BUCKET_NAME}/{SOURCE_PREFIX}")
print(f"Target: s3://{BUCKET_NAME}/{TARGET_PREFIX}")
print("=" * 70)
print()

# Initialize S3
s3 = boto3.client('s3', region_name=REGION)

# Step 1: List all JSON vectors
print("1. Listing JSON vectors...")
paginator = s3.get_paginator('list_objects_v2')
vectors_data = []
count = 0

for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=SOURCE_PREFIX):
    if 'Contents' not in page:
        continue

    for obj in page['Contents']:
        if obj['Key'].endswith('.json'):
            try:
                # Download vector
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                vector_json = json.loads(response['Body'].read())

                # Extract data in AWS format
                vectors_data.append({
                    'id': vector_json['id'],
                    'text': vector_json['text'],
                    'embedding': vector_json['embedding'],
                    'source_file': vector_json['metadata']['source_file'],
                    'chunk_index': vector_json['metadata']['chunk_index'],
                    'file_name': vector_json['metadata']['file_name'],
                    'folder_name': vector_json['metadata']['folder_name'],
                    'file_type': vector_json['metadata']['file_type']
                })

                count += 1
                if count % 100 == 0:
                    print(f"   Loaded {count} vectors...")

            except Exception as e:
                print(f"   Error loading {obj['Key']}: {e}")

print(f"   ✓ Loaded {len(vectors_data)} vectors")
print()

# Step 2: Create DataFrame
print("2. Creating DataFrame...")
df = pd.DataFrame(vectors_data)
print(f"   ✓ DataFrame shape: {df.shape}")
print()

# Step 3: Convert to Parquet with proper schema
print("3. Converting to Parquet format...")

# Define schema for AWS S3 Vector bucket
schema = pa.schema([
    ('id', pa.string()),
    ('text', pa.string()),
    ('embedding', pa.list_(pa.float32())),  # Vector must be float32 list
    ('source_file', pa.string()),
    ('chunk_index', pa.int64()),
    ('file_name', pa.string()),
    ('folder_name', pa.string()),
    ('file_type', pa.string())
])

# Convert DataFrame to PyArrow Table
table = pa.Table.from_pandas(df, schema=schema)
print(f"   ✓ Created PyArrow table: {table.num_rows} rows")
print()

# Step 4: Write to Parquet and upload
print("4. Writing Parquet file to S3...")
parquet_buffer = BytesIO()
pq.write_table(table, parquet_buffer)
parquet_buffer.seek(0)

# Upload Parquet file
parquet_key = f"{TARGET_PREFIX}vectors.parquet"
s3.upload_fileobj(
    parquet_buffer,
    BUCKET_NAME,
    parquet_key,
    ExtraArgs={
        'ContentType': 'application/octet-stream',
        'Metadata': {
            'format': 'parquet',
            'vector-dimension': '1024',
            'total-vectors': str(len(vectors_data))
        }
    }
)

print(f"   ✓ Uploaded: s3://{BUCKET_NAME}/{parquet_key}")
print()

# Step 5: Verify upload
file_size = parquet_buffer.tell() / 1024 / 1024
print("=" * 70)
print("✅ CONVERSION COMPLETE!")
print("=" * 70)
print(f"Total vectors: {len(vectors_data)}")
print(f"Parquet file: s3://{BUCKET_NAME}/{parquet_key}")
print(f"File size: {file_size:.2f} MB")
print()
print("Next Steps:")
print("1. Go to AWS Console S3 Vector bucket")
print("2. Create vector index")
print("3. Select data location: vectors-parquet/")
print("4. Configure:")
print("   - Vector dimensions: 1024")
print("   - Distance metric: COSINE")
print("=" * 70)
