#!/usr/bin/env python3
"""Upload course materials to S3"""

import boto3
import os
from pathlib import Path
import sys
sys.path.insert(0, '/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor')

from backend.config import config

print("=" * 70)
print("Uploading Course Materials to S3")
print("=" * 70)
print()

# Configuration
REGION = config.AWS_REGION
DOCS_BUCKET = config.S3_DOCUMENTS_BUCKET
BASE_DIR = "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor"

print(f"Region: {REGION}")
print(f"Bucket: {DOCS_BUCKET}")
print(f"Base directory: {BASE_DIR}")
print()

# Create S3 client
s3_client = boto3.client('s3', region_name=REGION)

def upload_directory(local_dir, s3_prefix):
    """Upload directory to S3"""
    local_path = Path(BASE_DIR) / local_dir
    
    if not local_path.exists():
        print(f"⚠ Directory not found: {local_dir}")
        return 0
    
    print(f"Uploading {local_dir}/ to s3://{DOCS_BUCKET}/{s3_prefix}/")
    
    uploaded = 0
    skipped = 0
    
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Skip certain files
            if file_path.name.startswith('.') or '__pycache__' in str(file_path):
                continue
            
            # Calculate S3 key
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{s3_prefix}/{relative_path}"
            
            try:
                # Upload file
                s3_client.upload_file(
                    str(file_path),
                    DOCS_BUCKET,
                    s3_key,
                    ExtraArgs={'ServerSideEncryption': 'AES256'}
                )
                uploaded += 1
                if uploaded % 10 == 0:
                    print(f"  Uploaded {uploaded} files...")
            except Exception as e:
                print(f"  ✗ Error uploading {file_path.name}: {e}")
                skipped += 1
    
    print(f"  ✓ Uploaded {uploaded} files ({skipped} skipped)")
    return uploaded

# Upload directories
total_uploaded = 0

print("1. Uploading Modules...")
total_uploaded += upload_directory("Modules", "modules")
print()

print("2. Uploading data...")
total_uploaded += upload_directory("data", "data")
print()

# List uploaded files
print("3. Verifying uploads...")
try:
    response = s3_client.list_objects_v2(
        Bucket=DOCS_BUCKET,
        MaxKeys=10
    )
    
    if 'Contents' in response:
        print(f"✓ Sample files in bucket:")
        for obj in response['Contents'][:5]:
            size_mb = obj['Size'] / (1024 * 1024)
            print(f"  • {obj['Key']} ({size_mb:.2f} MB)")
    else:
        print("⚠ No files found in bucket")
except Exception as e:
    print(f"✗ Error listing objects: {e}")

print()
print("=" * 70)
print(f"✅ Upload Complete! {total_uploaded} files uploaded")
print("=" * 70)
print()
print("View in AWS Console:")
print(f"https://s3.console.aws.amazon.com/s3/buckets/{DOCS_BUCKET}?region={REGION}")
print()
