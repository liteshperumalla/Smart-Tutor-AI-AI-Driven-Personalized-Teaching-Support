"""
Rebuild vector store with Bedrock embeddings + text content for AWS S3 Vector bucket
Uses Data_parsing.py chunking strategy but outputs to S3 with full text
"""
import os
import sys
import json
import boto3
from pathlib import Path

sys.path.insert(0, '/app')

# Import from Data_parsing
from Data_parsing import (
    load_documents_with_custom_readers,
    create_notebook_aware_parser,
    preprocess_text
)

# Import Bedrock embeddings
from backend.bedrock_embeddings import BedrockEmbeddings
from llama_index.core import Settings

# Configuration
S3_BUCKET = "smart-tutor-vector-bucket"
S3_REGION = "us-east-1"
CHUNKS_PREFIX = "chunks/"
MODULES_DIR = "/app/modules"

print("=" * 80)
print("REBUILD WITH BEDROCK EMBEDDINGS + TEXT CONTENT")
print("=" * 80)

# Initialize Bedrock
print("\n1. Initializing Bedrock embeddings...")
bedrock_embeddings = BedrockEmbeddings()
Settings.embed_model = bedrock_embeddings
print("   ✅ Bedrock Titan embeddings ready (1024-dim)")

# Initialize S3
s3_client = boto3.client('s3', region_name=S3_REGION)

# Load documents
print(f"\n2. Loading documents from {MODULES_DIR}...")
documents = load_documents_with_custom_readers(MODULES_DIR)
print(f"   ✅ Loaded {len(documents)} documents")

# Create parser
print("\n3. Creating notebook-aware parser...")
parser = create_notebook_aware_parser()

# Parse into chunks
print("\n4. Parsing documents into chunks...")
chunks = parser.get_nodes_from_documents(documents)
print(f"   ✅ Created {len(chunks)} chunks")

# Generate embeddings and upload
print(f"\n5. Generating Bedrock embeddings and uploading to S3...")
print(f"   (This will take ~15-20 minutes for {len(chunks)} chunks)")

uploaded = 0
failed = 0

for i, chunk in enumerate(chunks):
    try:
        if (i + 1) % 100 == 0:
            print(f"   Progress: {i+1}/{len(chunks)} chunks processed...")

        # Generate embedding
        embedding = bedrock_embeddings.get_text_embedding(chunk.text)

        # Create chunk data with TEXT included
        chunk_id = f"{chunk.metadata.get('file_name', 'chunk')}_{i:04d}"
        chunk_data = {
            'chunk_id': chunk_id,
            'text': chunk.text,  # ← KEY: Include actual text content
            'embedding': embedding,
            'source_file': chunk.metadata.get('file_path', ''),
            'chunk_index': i,
            'metadata': chunk.metadata
        }

        # Upload to S3
        s3_key = f"{CHUNKS_PREFIX}{chunk_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(chunk_data),
            ContentType='application/json'
        )

        uploaded += 1

    except Exception as e:
        failed += 1
        if failed <= 10:
            print(f"   Error on chunk {i}: {e}")

print(f"\n6. Upload Complete!")
print(f"   ✅ Successfully uploaded: {uploaded}")
print(f"   ❌ Failed: {failed}")
print(f"\n7. Creating metadata...")

metadata = {
    'total_vectors': uploaded,
    'embedding_dimension': 1024,
    'embedding_model': 'amazon.titan-embed-text-v2:0',
    'distance_metric': 'cosine',
    'has_text_content': True,  # ← Important flag
}

s3_client.put_object(
    Bucket=S3_BUCKET,
    Key='metadata.json',
    Body=json.dumps(metadata, indent=2),
    ContentType='application/json'
)

print(f"\n{'='*80}")
print(f"✅ COMPLETE! {uploaded} chunks with text + Bedrock embeddings in S3")
print(f"{'='*80}")
print(f"\nNext: Restart backend to use the new chunks")
