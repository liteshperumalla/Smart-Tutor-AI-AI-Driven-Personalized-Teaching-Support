"""
Rebuild S3 Vector Index with correct chunk paths
"""
import boto3
import json
import pickle
import numpy as np
from pathlib import Path
import os

# Configuration
S3_BUCKET = "smart-tutor-vector-bucket"
S3_REGION = "us-east-1"
VECTORS_PREFIX = "vectors/"
INDEX_OUTPUT = "vector_index/s3_vector_index.pkl"

print("Initializing S3 client...")
s3_client = boto3.client('s3', region_name=S3_REGION)

print(f"Scanning S3 bucket: {S3_BUCKET}/{VECTORS_PREFIX}")

# Collect all chunk files
chunk_files = []
paginator = s3_client.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=VECTORS_PREFIX)

for page in pages:
    if 'Contents' not in page:
        continue
    for obj in page['Contents']:
        key = obj['Key']
        if key.endswith('.json') and '/chunk_' in key:
            chunk_files.append(key)

print(f"Found {len(chunk_files)} chunk files in S3")

# Load chunks and build index
vectors = []
metadata_list = []
chunk_ids = []

print("Loading chunks and building index...")
for i, chunk_key in enumerate(chunk_files):
    if i % 100 == 0:
        print(f"Processed {i}/{len(chunk_files)} chunks...")

    try:
        # Download chunk
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=chunk_key)
        chunk_data = json.loads(response['Body'].read().decode('utf-8'))

        # Extract embedding
        if 'embedding' in chunk_data and chunk_data['embedding']:
            embedding = chunk_data['embedding']
            if isinstance(embedding, list):
                embedding = np.array(embedding, dtype=np.float32)

            vectors.append(embedding)

            # Store metadata with S3 key
            metadata = {
                's3_key': chunk_key,
                'text': chunk_data.get('text', ''),
                'source_file': chunk_data.get('source_file', ''),
                'page_number': chunk_data.get('page_number'),
                'slide_number': chunk_data.get('slide_number'),
            }
            metadata_list.append(metadata)

            # Chunk ID from S3 key
            chunk_id = chunk_key.replace(VECTORS_PREFIX, '').replace('.json', '')
            chunk_ids.append(chunk_id)

    except Exception as e:
        print(f"Error processing {chunk_key}: {e}")
        continue

print(f"\nLoaded {len(vectors)} valid vectors")

# Convert to numpy array
if vectors:
    vectors_array = np.vstack(vectors)
    print(f"Vectors shape: {vectors_array.shape}")

    # Build index structure
    index_data = {
        'vectors': vectors_array,
        'metadata': metadata_list,
        'chunk_ids': chunk_ids,
        'embedding_dim': vectors_array.shape[1],
        'total_vectors': len(vectors),
    }

    # Save locally first
    local_index_path = '/tmp/s3_vector_index.pkl'
    print(f"\nSaving index to {local_index_path}...")
    with open(local_index_path, 'wb') as f:
        pickle.dump(index_data, f)

    # Upload to S3
    print(f"Uploading index to S3: s3://{S3_BUCKET}/{INDEX_OUTPUT}")
    s3_client.upload_file(local_index_path, S3_BUCKET, INDEX_OUTPUT)

    print(f"\n✓ Index rebuilt successfully!")
    print(f"  Total vectors: {len(vectors)}")
    print(f"  Embedding dimension: {vectors_array.shape[1]}")
    print(f"  S3 location: s3://{S3_BUCKET}/{INDEX_OUTPUT}")
else:
    print("ERROR: No vectors found!")
