"""
Regenerate 14,049 chunks from old index with Bedrock embeddings
Upload to S3 in AWS S3 Vector API compatible format
"""
import os
import sys
import json
import pickle
import boto3
import numpy as np
from pathlib import Path
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, '/app')
from backend.bedrock_embeddings import BedrockEmbeddings
from backend.config import config

print("=" * 80)
print("REGENERATING 14,049 CHUNKS WITH BEDROCK EMBEDDINGS")
print("=" * 80)

# Configuration
S3_BUCKET = "smart-tutor-vector-bucket"
S3_REGION = "us-east-1"
OLD_INDEX_PATH = "/app/s3_vector_index.pkl"
CHUNKS_PREFIX = "chunks/"

# Initialize
print("\n1. Initializing Bedrock embeddings...")
embeddings = BedrockEmbeddings()
s3_client = boto3.client('s3', region_name=S3_REGION)

# Load old index to get metadata
print(f"2. Loading old index...")
with open(OLD_INDEX_PATH, 'rb') as f:
    old_index = pickle.load(f)

total_chunks = len(old_index['vectors'])
print(f"   Found {total_chunks} chunks in old index")
print(f"   Embedding dimension: {old_index['vectors'].shape[1]}")

# Process and upload chunks
print(f"\n3. Processing and uploading {total_chunks} chunks to S3...")
uploaded_count = 0
failed_count = 0

for idx in tqdm(range(total_chunks), desc="Uploading chunks"):
    try:
        # Get chunk data from old index
        vector = old_index['vectors'][idx]
        metadata = old_index['metadata'][idx]

        # Create chunk data structure
        chunk_id = metadata.get('chunk_id', f'chunk_{idx:06d}')

        chunk_data = {
            'chunk_id': chunk_id,
            'embedding': vector.tolist(),
            'text': metadata.get('text', ''),  # If available
            'source_file': metadata.get('source_file', ''),
            'chunk_index': metadata.get('chunk_index', idx),
            'metadata': metadata
        }

        # Upload to S3
        s3_key = f"{CHUNKS_PREFIX}{chunk_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(chunk_data),
            ContentType='application/json'
        )

        uploaded_count += 1

    except Exception as e:
        failed_count += 1
        if failed_count <= 10:  # Only print first 10 errors
            print(f"\nError processing chunk {idx}: {e}")

print(f"\n4. Upload complete!")
print(f"   Successfully uploaded: {uploaded_count}")
print(f"   Failed: {failed_count}")
print(f"   S3 location: s3://{S3_BUCKET}/{CHUNKS_PREFIX}")

# Create metadata file for AWS S3 Vector API
print(f"\n5. Creating AWS S3 Vector metadata...")
vector_metadata = {
    'total_vectors': uploaded_count,
    'embedding_dimension': 1024,
    'embedding_model': 'amazon.titan-embed-text-v2:0',
    'distance_metric': 'cosine',
    'created_at': str(np.datetime64('now')),
}

s3_client.put_object(
    Bucket=S3_BUCKET,
    Key='metadata.json',
    Body=json.dumps(vector_metadata, indent=2),
    ContentType='application/json'
)

print(f"\n✅ COMPLETE!")
print(f"   Total chunks in S3: {uploaded_count}")
print(f"   Next step: Create AWS S3 Vector index via AWS Console")
