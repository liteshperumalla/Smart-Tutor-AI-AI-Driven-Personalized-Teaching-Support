#!/usr/bin/env python3
"""Create S3 buckets for Smart AI Tutor"""

import boto3
from botocore.exceptions import ClientError
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.config import config

print("=" * 70)
print("Creating S3 Buckets for Smart AI Tutor")
print("=" * 70)
print()

# Configuration
REGION = config.AWS_REGION
DOCS_BUCKET = config.S3_DOCUMENTS_BUCKET
UPLOADS_BUCKET = config.S3_UPLOADS_BUCKET

# Validate configuration
if not REGION:
    print("✗ Error: AWS_REGION is not set in config.")
    sys.exit(1)
if not DOCS_BUCKET:
    print("✗ Error: S3_DOCUMENTS_BUCKET is not set in config.")
    sys.exit(1)
if not UPLOADS_BUCKET:
    print("✗ Error: S3_UPLOADS_BUCKET is not set in config.")
    sys.exit(1)

# Basic bucket name validation (S3 rules are complex, this is a basic check)
if not (3 <= len(DOCS_BUCKET) <= 63 and all(c.islower() or c.isdigit() or c == '-' for c in DOCS_BUCKET)):
    print(f"✗ Error: Invalid S3_DOCUMENTS_BUCKET name: {DOCS_BUCKET}. Must be 3-63 lowercase chars/digits/hyphens.")
    sys.exit(1)
if not (3 <= len(UPLOADS_BUCKET) <= 63 and all(c.islower() or c.isdigit() or c == '-' for c in UPLOADS_BUCKET)):
    print(f"✗ Error: Invalid S3_UPLOADS_BUCKET name: {UPLOADS_BUCKET}. Must be 3-63 lowercase chars/digits/hyphens.")
    sys.exit(1)

print(f"Region: {REGION}")
print(f"Documents bucket: {DOCS_BUCKET}")
print(f"Uploads bucket: {UPLOADS_BUCKET}")
print()

# Create S3 client
try:
    s3_client = boto3.client('s3', region_name=REGION)
    print("✓ AWS S3 client initialized")
    print()
except Exception as e:
    print(f"✗ Failed to initialize S3 client: {e}")
    sys.exit(1)

def create_bucket(bucket_name, region):
    """Create S3 bucket"""
    try:
        if region == 'us-east-1':
            # us-east-1 doesn't need LocationConstraint
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"✓ Created bucket: {bucket_name}")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'BucketAlreadyOwnedByYou':
            print(f"⚠ Bucket already exists (owned by you): {bucket_name}")
            return True
        elif error_code == 'BucketAlreadyExists':
            print(f"✗ Bucket name taken (owned by someone else): {bucket_name}")
            return False
        else:
            print(f"✗ Error creating bucket {bucket_name}: {e}")
            return False

def enable_versioning(bucket_name):
    """Enable versioning on bucket"""
    try:
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        print(f"  ✓ Versioning enabled on {bucket_name}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to enable versioning: {e}")
        return False

def set_lifecycle_policy(bucket_name):
    """Set lifecycle policy to delete old versions"""
    try:
        lifecycle_config = {
            'Rules': [
                {
                    'Id': 'DeleteOldVersions',
                    'Status': 'Enabled',
                    'NoncurrentVersionExpiration': {
                        'NoncurrentDays': 90
                    }
                }
            ]
        }
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_config
        )
        print(f"  ✓ Lifecycle policy set (delete old versions after 90 days)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to set lifecycle policy: {e}")
        return False

# Create buckets
print("1. Creating documents bucket...")
if create_bucket(DOCS_BUCKET, REGION):
    enable_versioning(DOCS_BUCKET)
    set_lifecycle_policy(DOCS_BUCKET)
print()

print("2. Creating uploads bucket...")
if not create_bucket(UPLOADS_BUCKET, REGION):
    print(f"✗ Failed to create uploads bucket: {UPLOADS_BUCKET}. Exiting.")
    sys.exit(1)
print()

# List buckets
print("3. Verifying buckets...")
try:
    response = s3_client.list_buckets()
    target_buckets = {DOCS_BUCKET, UPLOADS_BUCKET}
    our_buckets = [b['Name'] for b in response['Buckets'] 
                   if b['Name'] in target_buckets]
    print(f"✓ Found {len(our_buckets)} Smart AI Tutor buckets:")
    for bucket in our_buckets:
        print(f"  • s3://{bucket}")
except Exception as e:
    print(f"✗ Error listing buckets: {e}")

print()
print("=" * 70)
print("✅ S3 Setup Complete!")
print("=" * 70)
print()
print("Next steps:")
print("1. Upload course materials:")
print(f"   python upload_to_s3.py")
print()
print("2. View buckets in console:")
print(f"   https://s3.console.aws.amazon.com/s3/buckets?region={REGION}")
print()
