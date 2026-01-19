"""
Parallel upload of 14,049 chunks to S3 with Bedrock embeddings
Uses ThreadPoolExecutor for 10x faster uploads
"""
import os
import sys
import json
import pickle
import boto3
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm

# Configuration
sys.path.insert(0, '/app')
S3_BUCKET = "smart-tutor-vector-bucket"
S3_REGION = "us-east-1"
OLD_INDEX_PATH = "/app/s3_vector_index.pkl"
CHUNKS_PREFIX = "chunks/"
MAX_WORKERS = 50  # Parallel upload threads

print("=" * 80)
print("PARALLEL UPLOAD: 14,049 CHUNKS TO S3")
print("=" * 80)

# Initialize S3 client (thread-safe)
s3_client = boto3.client('s3', region_name=S3_REGION)

# Load old index
print(f"\n1. Loading index with 14,049 chunks...")
with open(OLD_INDEX_PATH, 'rb') as f:
    old_index = pickle.load(f)

total_chunks = len(old_index['vectors'])
print(f"   Total chunks: {total_chunks}")
print(f"   Embedding dimension: {old_index['vectors'].shape[1]}")

# Thread-safe counters
upload_lock = Lock()
uploaded_count = 0
failed_count = 0
failed_chunks = []

def upload_chunk(idx):
    """Upload a single chunk to S3"""
    global uploaded_count, failed_count

    try:
        # Get chunk data
        vector = old_index['vectors'][idx]
        metadata = old_index['metadata'][idx]
        chunk_id = metadata.get('chunk_id', f'chunk_{idx:06d}')

        # Create chunk data
        chunk_data = {
            'chunk_id': chunk_id,
            'embedding': vector.tolist(),
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

        with upload_lock:
            uploaded_count += 1

        return True, idx, None

    except Exception as e:
        with upload_lock:
            failed_count += 1
        return False, idx, str(e)

# Parallel upload
print(f"\n2. Uploading {total_chunks} chunks in parallel ({MAX_WORKERS} workers)...")
print(f"   This should take ~5-10 minutes...")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    # Submit all tasks
    futures = {executor.submit(upload_chunk, idx): idx for idx in range(total_chunks)}

    # Progress bar
    with tqdm(total=total_chunks, desc="Uploading", unit="chunks") as pbar:
        for future in as_completed(futures):
            success, idx, error = future.result()
            if not success:
                failed_chunks.append((idx, error))
                if len(failed_chunks) <= 10:
                    print(f"\nError on chunk {idx}: {error}")
            pbar.update(1)

print(f"\n3. Upload Complete!")
print(f"   ✅ Successfully uploaded: {uploaded_count}")
print(f"   ❌ Failed: {failed_count}")

if failed_count > 0:
    print(f"\n   First 10 failures:")
    for idx, error in failed_chunks[:10]:
        print(f"      Chunk {idx}: {error}")

# Create metadata file
print(f"\n4. Creating metadata file...")
metadata = {
    'total_vectors': uploaded_count,
    'embedding_dimension': 1024,
    'embedding_model': 'amazon.titan-embed-text-v2:0',
    'distance_metric': 'cosine',
    'chunk_prefix': CHUNKS_PREFIX,
    'created_at': str(np.datetime64('now')),
}

s3_client.put_object(
    Bucket=S3_BUCKET,
    Key='metadata.json',
    Body=json.dumps(metadata, indent=2),
    ContentType='application/json'
)

print(f"\n{'='*80}")
print(f"✅ COMPLETE! {uploaded_count} chunks uploaded to S3")
print(f"{'='*80}")
print(f"\nS3 Location: s3://{S3_BUCKET}/{CHUNKS_PREFIX}")
print(f"\nNext steps:")
print(f"1. Verify upload: aws s3 ls s3://{S3_BUCKET}/{CHUNKS_PREFIX} --recursive | wc -l")
print(f"2. Create AWS S3 Vector index via Console (if using Vector API)")
print(f"3. Or rebuild local index from S3 chunks")
