"""
Rebuild vector index from S3 chunks
Creates a local index file that the backend can load
"""
import os
import sys
import json
import pickle
import boto3
import numpy as np
from tqdm import tqdm

sys.path.insert(0, '/app')

# Configuration
S3_BUCKET = "smart-tutor-vector-bucket"
S3_REGION = "us-east-1"
CHUNKS_PREFIX = "chunks/"
INDEX_OUTPUT_PATH = "/app/s3_vector_index.pkl"

print("=" * 80)
print("REBUILD INDEX FROM S3 CHUNKS")
print("=" * 80)

# Initialize S3
s3_client = boto3.client('s3', region_name=S3_REGION)

# List all chunks in S3
print(f"\n1. Listing chunks from s3://{S3_BUCKET}/{CHUNKS_PREFIX}...")
paginator = s3_client.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=CHUNKS_PREFIX)

chunk_keys = []
for page in pages:
    if 'Contents' in page:
        for obj in page['Contents']:
            if obj['Key'].endswith('.json'):
                chunk_keys.append(obj['Key'])

print(f"   Found {len(chunk_keys)} chunks")

# Load chunks and build index
print(f"\n2. Loading chunks and building index...")
vectors = []
metadata_list = []

for i, chunk_key in enumerate(tqdm(chunk_keys, desc="Loading")):
    try:
        # Download chunk
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=chunk_key)
        chunk_data = json.loads(response['Body'].read().decode('utf-8'))

        # Extract data
        embedding = chunk_data.get('embedding', [])
        if embedding:
            vectors.append(np.array(embedding, dtype=np.float32))

            # Build metadata
            meta = {
                'chunk_id': chunk_data.get('chunk_id'),
                'source_file': chunk_data.get('source_file', ''),
                'chunk_index': chunk_data.get('chunk_index', i),
                's3_key': chunk_key,
            }

            # Add additional metadata fields
            if 'metadata' in chunk_data:
                meta.update(chunk_data['metadata'])

            metadata_list.append(meta)

    except Exception as e:
        if i < 10:  # Only print first 10 errors
            print(f"\nError loading {chunk_key}: {e}")
        continue

print(f"\n3. Loaded {len(vectors)} vectors")

# Build index
if vectors:
    vectors_array = np.vstack(vectors)
    print(f"   Vectors shape: {vectors_array.shape}")

    index_data = {
        'vectors': vectors_array,
        'metadata': metadata_list,
        'count': len(vectors),
        'dimension': vectors_array.shape[1],
    }

    # Save index
    print(f"\n4. Saving index to {INDEX_OUTPUT_PATH}...")
    with open(INDEX_OUTPUT_PATH, 'wb') as f:
        pickle.dump(index_data, f)

    print(f"\n{'='*80}")
    print(f"✅ INDEX REBUILT SUCCESSFULLY!")
    print(f"{'='*80}")
    print(f"Total vectors: {len(vectors)}")
    print(f"Embedding dimension: {vectors_array.shape[1]}")
    print(f"Index file: {INDEX_OUTPUT_PATH}")
    print(f"\nRestart the backend to load the new index.")
else:
    print("\nERROR: No vectors loaded!")
    sys.exit(1)
