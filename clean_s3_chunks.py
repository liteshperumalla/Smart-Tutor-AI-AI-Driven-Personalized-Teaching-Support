#!/usr/bin/env python3
"""Clean all chunks from S3 bucket before reprocessing"""

import boto3
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.config import config

BUCKET = config.S3_DOCUMENTS_BUCKET
REGION = config.AWS_REGION

s3 = boto3.client('s3', region_name=REGION)

print("=" * 70)
print("CLEANING S3 CHUNKS")
print("=" * 70)
print(f"Bucket: {BUCKET}")
print()

# List all objects in chunks/
paginator = s3.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=BUCKET, Prefix='chunks/')

objects_to_delete = []
for page in pages:
    if 'Contents' not in page:
        continue

    for obj in page['Contents']:
        objects_to_delete.append({'Key': obj['Key']})

if not objects_to_delete:
    print("No objects to delete")
    exit(0)

print(f"Found {len(objects_to_delete)} objects to delete")
print()

# Delete in batches of 1000 (AWS limit)
deleted_count = 0
error_count = 0
for i in range(0, len(objects_to_delete), 1000):
    batch = objects_to_delete[i:i+1000]
    response = s3.delete_objects(
        Bucket=BUCKET,
        Delete={'Objects': batch}
    )
    
    if 'Deleted' in response:
        deleted_count += len(response['Deleted'])
    
    if 'Errors' in response:
        error_count += len(response['Errors'])
        for error in response['Errors']:
            print(f"  ✗ Error deleting {error['Key']}: {error['Message']}")

    print(f"Deleted {deleted_count}/{len(objects_to_delete)} objects...")

print()
print("=" * 70)
print(f"✅ CLEANED {deleted_count} OBJECTS FROM S3")
if error_count > 0:
    print(f"  (with {error_count} errors)")
print("=" * 70)
