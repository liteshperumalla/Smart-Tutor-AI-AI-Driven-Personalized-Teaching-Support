"""
Rebuild S3 Vector Index from all chunks in S3
Reads chunks from s3://smart-tutor-vector-bucket/chunks/
"""
import boto3
import json
import pickle
import numpy as np
from pathlib import Path
import os

print("="*80)
print("REBUILDING S3 VECTOR INDEX")
print("="*80)

# Configuration
S3_BUCKET = "smart-tutor-vector-bucket"
S3_REGION = "us-east-1"
CHUNKS_PREFIX = "chunks/"
INDEX_OUTPUT = "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/vector_index/s3_vector_index.pkl"

print(f"\n1. Initializing S3 client...")
s3_client = boto3.client('s3', region_name=S3_REGION)
print("   ✅ S3 client ready")

print(f"\n2. Scanning S3 bucket: s3://{S3_BUCKET}/{CHUNKS_PREFIX}")

# Collect all chunk files
chunk_files = []
paginator = s3_client.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=CHUNKS_PREFIX)

for page in pages:
    if 'Contents' not in page:
        continue
    for obj in page['Contents']:
        key = obj['Key']
        if key.endswith('.json'):
            chunk_files.append(key)

print(f"   ✅ Found {len(chunk_files)} chunk files in S3")

# Load chunks and build index
vectors = []
metadata_list = []
chunk_ids = []

print(f"\n3. Loading chunks and building index...")
for i, chunk_key in enumerate(chunk_files):
    if (i + 1) % 500 == 0:
        print(f"   → Processed {i + 1}/{len(chunk_files)} chunks...")

    try:
        # Download chunk
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=chunk_key)
        chunk_data = json.loads(response['Body'].read().decode('utf-8'))

        # Extract data
        chunk_id = chunk_data.get('chunk_id')
        embedding = chunk_data.get('embedding')
        source_file = chunk_data.get('source_file', 'unknown')
        chunk_index = chunk_data.get('chunk_index', i)
        text = chunk_data.get('text', '')  # Include text for verification

        if not chunk_id or not embedding:
            print(f"   ✗ Skipping {chunk_key}: missing chunk_id or embedding")
            continue

        # Add to index
        vectors.append(embedding)
        chunk_ids.append(chunk_id)
        metadata_list.append({
            'chunk_id': chunk_id,
            's3_key': chunk_key,
            'source_file': source_file,
            'chunk_index': chunk_index,
            'has_text': len(text) > 0
        })

    except Exception as e:
        print(f"   ✗ Error processing {chunk_key}: {e}")
        continue

print(f"   ✅ Processed {len(vectors)} chunks successfully")

if len(vectors) == 0:
    print("\n❌ ERROR: No vectors found! Cannot create index.")
    exit(1)

# Convert to numpy array
vectors_array = np.array(vectors, dtype=np.float32)
print(f"\n4. Index statistics:")
print(f"   → Total chunks: {len(vectors)}")
print(f"   → Vector dimensions: {vectors_array.shape[1]}")
print(f"   → Chunks with text: {sum(1 for m in metadata_list if m['has_text'])}")

# Create index structure
index_data = {
    'vectors': vectors_array,
    'chunk_ids': chunk_ids,
    'metadata': metadata_list,
    'embedding_dim': vectors_array.shape[1],
    'total_chunks': len(vectors)
}

# Save index
print(f"\n5. Saving index to {INDEX_OUTPUT}...")
os.makedirs(os.path.dirname(INDEX_OUTPUT), exist_ok=True)
with open(INDEX_OUTPUT, 'wb') as f:
    pickle.dump(index_data, f)

print(f"   ✅ Index saved successfully")

print(f"\n{'='*80}")
print(f"✅ INDEX REBUILD COMPLETE!")
print(f"{'='*80}")
print(f"Total chunks indexed: {len(vectors)}")
print(f"Embedding dimensions: {vectors_array.shape[1]}")
print(f"Index file: {INDEX_OUTPUT}")
print(f"\nNext: Restart backend to load the new index")
