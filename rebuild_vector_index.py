#!/usr/bin/env python3
"""Rebuild vector index from all S3 chunks"""

import sys
import boto3
import json
import numpy as np
import pickle
from pathlib import Path

sys.path.insert(0, '.')
from backend.config import config

print("=" * 70)
print("REBUILDING VECTOR INDEX FROM S3")
print("=" * 70)
print()

BUCKET = config.S3_DOCUMENTS_BUCKET
REGION = config.AWS_REGION
CACHE_FILE = "s3_vector_index.pkl"  # Default cache file

s3 = boto3.client('s3', region_name=REGION)

print(f"S3 Bucket: {BUCKET}")
print(f"Cache file: {CACHE_FILE}")
print()

# Load all vectors from S3
print("Loading vectors from S3...")
paginator = s3.get_paginator('list_objects_v2')

vectors = []
metadata = []
count = 0

for page in paginator.paginate(Bucket=BUCKET, Prefix='chunks/modules/'):
    if 'Contents' not in page:
        continue
    
    for obj in page['Contents']:
        if obj['Key'].endswith('.vector.json'):
            try:
                response = s3.get_object(Bucket=BUCKET, Key=obj['Key'])
                vector_data = json.loads(response['Body'].read())
                
                vectors.append(vector_data['embedding'])
                metadata.append({
                    'chunk_id': vector_data['chunk_id'],
                    'source_file': vector_data['source_file'],
                    'chunk_index': vector_data['chunk_index']
                })
                
                count += 1
                if count % 1000 == 0:
                    print(f"  Loaded {count} vectors...")
                    
            except Exception as e:
                print(f"  Warning: Failed to load {obj['Key']}: {str(e)[:50]}")

print()
print(f"Loaded {len(vectors)} vectors")
print(f"Vector dimension: {len(vectors[0]) if vectors else 0}")
print()

# Create index
print("Creating vector index...")
vectors_array = np.array(vectors, dtype=np.float32)

# Normalize for cosine similarity
norms = np.linalg.norm(vectors_array, axis=1, keepdims=True)
vectors_normalized = vectors_array / norms

index_data = {
    'vectors': vectors_normalized,
    'metadata': metadata,
    'count': len(vectors),
    'dimension': len(vectors[0]) if vectors else 0
}

print(f"Index created: {len(vectors)} vectors")
print()

# Save to cache
print(f"Saving to {CACHE_FILE}...")
with open(CACHE_FILE, 'wb') as f:
    pickle.dump(index_data, f)

file_size = Path(CACHE_FILE).stat().st_size / 1024 / 1024
print(f"Cache file size: {file_size:.1f} MB")
print()

print("=" * 70)
print("✅ VECTOR INDEX REBUILT SUCCESSFULLY!")
print(f"   Total vectors: {len(vectors):,}")
print(f"   Cache file: {CACHE_FILE}")
print("=" * 70)
