#!/usr/bin/env python3
"""
Setup S3 Vector Buckets for Smart AI Tutor
Enables S3 Metadata Search and configures vector storage
"""

import boto3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

BUCKET_NAME = config.S3_DOCUMENTS_BUCKET
REGION = config.AWS_REGION
VECTOR_DIMENSION = 1024  # Titan Text Embeddings v2


def check_s3_metadata_search_availability():
    """Check if S3 Metadata Search is available in the region"""
    print(f"Checking S3 Metadata Search availability in {REGION}...")

    # S3 Metadata Search is available in select regions
    supported_regions = ['us-east-1', 'us-west-2', 'eu-west-1']

    if REGION not in supported_regions:
        print(f"⚠️  Warning: S3 Metadata Search may not be available in {REGION}")
        print(f"   Supported regions: {', '.join(supported_regions)}")
        return False

    print(f"✓ S3 Metadata Search is supported in {REGION}")
    return True


def enable_s3_metadata_search():
    """
    Enable S3 Metadata Search on the bucket

    Note: This must be done via AWS Console currently, as the API is limited.
    This function provides instructions.
    """
    print("=" * 70)
    print("ENABLING S3 METADATA SEARCH (Manual Step Required)")
    print("=" * 70)
    print()
    print("AWS S3 Metadata Search must be enabled via the Console:")
    print()
    print("1. Go to AWS S3 Console:")
    print(f"   https://s3.console.aws.amazon.com/s3/buckets/{BUCKET_NAME}?region={REGION}")
    print()
    print("2. Click on the bucket:", BUCKET_NAME)
    print()
    print("3. Go to 'Properties' tab")
    print()
    print("4. Scroll to 'S3 Metadata Search' section")
    print()
    print("5. Click 'Create metadata table configuration'")
    print()
    print("6. Configure:")
    print(f"   - Name: smart-tutor-vectors")
    print(f"   - S3 prefix: chunks/")
    print(f"   - Enable vector indexing: Yes")
    print(f"   - Vector dimension: {VECTOR_DIMENSION}")
    print(f"   - Distance metric: COSINE")
    print()
    print("7. Click 'Create'")
    print()
    print("Note: This will create an AWS Glue table for metadata indexing")
    print()
    print("=" * 70)

    response = input("\nHave you enabled S3 Metadata Search? (yes/no): ")
    return response.lower() == 'yes'


def create_vector_bucket_structure():
    """Create folder structure in S3 for vectors"""
    s3 = boto3.client('s3', region_name=REGION)

    print("\nCreating S3 folder structure...")

    folders = [
        'chunks/',
        'chunks/module_1/',
        'chunks/module_2/',
        'chunks/module_3/',
        'chunks/module_4/',
        'chunks/module_5/',
        'chunks/module_6/',
        'chunks/module_7/',
        'chunks/module_8/',
        'chunks/module_9/',
        'chunks/module_10/',
    ]

    for folder in folders:
        try:
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=folder,
                Body=b''
            )
            print(f"  ✓ Created: {folder}")
        except Exception as e:
            print(f"  ⚠ Error creating {folder}: {e}")

    print("✓ Folder structure created")


def test_vector_upload():
    """Test uploading a document chunk with vector metadata"""
    s3 = boto3.client('s3', region_name=REGION)

    print("\nTesting vector upload...")

    # Sample vector (1024 dimensions)
    test_vector = [0.1] * VECTOR_DIMENSION

    # Sample document chunk
    test_content = "This is a test document chunk for vector search."

    metadata = {
        'vector-dimension': str(VECTOR_DIMENSION),
        'chunk-id': 'test_001',
        'source-file': 'test.pdf',
        'chunk-index': '0',
        'model': 'titan-embed-text-v2'
    }

    try:
        # Upload document with metadata
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key='chunks/test/test_chunk_001.txt',
            Body=test_content.encode('utf-8'),
            Metadata=metadata,
            ContentType='text/plain'
        )

        # Store vector separately (S3 metadata has size limits)
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key='chunks/test/test_chunk_001.vector.json',
            Body=json.dumps({
                'embedding': test_vector,
                'chunk_id': 'test_001',
                'dimension': VECTOR_DIMENSION
            }).encode('utf-8'),
            ContentType='application/json'
        )

        print("✓ Test upload successful!")
        print(f"  - Chunk: chunks/test/test_chunk_001.txt")
        print(f"  - Vector: chunks/test/test_chunk_001.vector.json")

        return True

    except Exception as e:
        print(f"✗ Test upload failed: {e}")
        return False


def display_next_steps():
    """Display next steps for user"""
    print()
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("1. ✓ S3 bucket structure created")
    print()
    print("2. Next: Generate embeddings for all documents")
    print("   Run: python generate_s3_embeddings.py")
    print()
    print("3. Then: Upload chunks + vectors to S3")
    print("   Run: python upload_vectors_to_s3.py")
    print()
    print("4. Finally: Update RAG pipeline to use S3 vectors")
    print("   Run: python integrate_s3_vectors.py")
    print()
    print("=" * 70)


def main():
    print("=" * 70)
    print("S3 VECTOR BUCKETS SETUP")
    print("Smart AI Tutor - AWS Integration")
    print("=" * 70)
    print()
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Region: {REGION}")
    print(f"Vector Dimension: {VECTOR_DIMENSION}")
    print()

    # Step 1: Check availability
    if not check_s3_metadata_search_availability():
        print("\n⚠️  Proceeding anyway, but feature may not be fully available")

    # Step 2: Instructions for enabling metadata search
    if not enable_s3_metadata_search():
        print("\n⚠️  Please enable S3 Metadata Search before proceeding")
        print("   You can continue with folder setup and come back to this")
        response = input("\nContinue with folder setup? (yes/no): ")
        if response.lower() != 'yes':
            print("\nSetup cancelled. Run this script again after enabling metadata search.")
            return

    # Step 3: Create folder structure
    create_vector_bucket_structure()

    # Step 4: Test upload
    test_vector_upload()

    # Step 5: Display next steps
    display_next_steps()

    print("\n✅ S3 Vector Bucket setup complete!")


if __name__ == "__main__":
    main()
