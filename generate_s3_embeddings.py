#!/usr/bin/env python3
"""
Generate embeddings for all documents and upload to S3 with vector metadata
"""

import boto3
import json
import sys
from pathlib import Path
from typing import List, Dict
import time

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.config import config
from backend.bedrock_embeddings import BedrockEmbeddings
from backend.logger import get_logger
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter

try:
    import tiktoken
    TOKENIZER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    logger.warning("tiktoken not found, falling back to word count for token estimation.")
    TOKENIZER = None

logger = get_logger(__name__)

BUCKET_NAME = config.S3_DOCUMENTS_BUCKET
REGION = config.AWS_REGION
CHUNK_SIZE = 512
CHUNK_OVERLAP = 102


class S3VectorUploader:
    """Upload document chunks with embeddings to S3"""

    def __init__(self):
        self.s3 = boto3.client('s3', region_name=REGION)
        self.embeddings = BedrockEmbeddings(
            model_id=config.BEDROCK_EMBEDDING_MODEL_ID,
            region=REGION
        )
        self.splitter = SentenceSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        self.uploaded_count = 0
        self.total_cost = 0.0

    def process_local_documents(self, data_dir: str = "./data"):
        """Process documents from local directory"""
        print(f"Processing documents from: {data_dir}")
        print()

        data_path = Path(data_dir)
        if not data_path.exists():
            print(f"✗ Directory not found: {data_dir}")
            return

        # Find all supported files
        file_extensions = ['.pdf', '.txt', '.md', '.docx', '.pptx', '.ipynb']
        files = []
        for ext in file_extensions:
            files.extend(list(data_path.rglob(f'*{ext}')))

        print(f"Found {len(files)} files to process")
        print()

        if len(files) == 0:
            print("No files found. Check the directory path.")
            return

        # Process in batches to avoid overwhelming the system
        batch_size = 10
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1} ({len(batch)} files)...")

            for file_path in batch:
                try:
                    self.process_single_file(file_path, data_dir)
                except Exception as e:
                    print(f"  ✗ Error processing {file_path.name}: {e}")

            # Small delay between batches
            if i + batch_size < len(files):
                print(f"  Processed {min(i + batch_size, len(files))}/{len(files)} files")
                time.sleep(1)

        print()
        print(f"✅ Processing complete!")
        print(f"   Uploaded: {self.uploaded_count} chunks")
        print(f"   Estimated cost: ${self.total_cost:.4f}")

    def process_single_file(self, file_path: Path, base_dir: str):
        """Process a single file and upload chunks with embeddings"""
        relative_path = file_path.relative_to(base_dir)

        # Read document
        try:
            reader = SimpleDirectoryReader(input_files=[str(file_path)])
            documents = reader.load_data()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return

        if not documents:
            return

        # Split into chunks
        nodes = self.splitter.get_nodes_from_documents(documents)

        if not nodes:
            return

        print(f"  Processing: {file_path.name} ({len(nodes)} chunks)")

        # Generate embeddings for all chunks
        texts = [node.get_content() for node in nodes]
        all_embeddings = []
        SUB_BATCH_SIZE = 16  # Titan supports up to 16 texts per request
        DELAY_BETWEEN_BATCHES_MS = 200 # Milliseconds
        MAX_RETRIES = 5
        
        for i in range(0, len(texts), SUB_BATCH_SIZE):
            sub_batch_texts = texts[i:i + SUB_BATCH_SIZE]
            
            for attempt in range(MAX_RETRIES):
                try:
                    sub_batch_embeddings = self.embeddings.encode(sub_batch_texts)
                    all_embeddings.extend(sub_batch_embeddings)
                    break # Success, break retry loop
                except Exception as e:
                    logger.warning(f"Embedding sub-batch failed (attempt {attempt+1}/{MAX_RETRIES}): {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep((2 ** attempt) * (DELAY_BETWEEN_BATCHES_MS / 1000)) # Exponential backoff
                    else:
                        logger.error(f"Max retries reached for embedding sub-batch. Skipping {len(sub_batch_texts)} texts.")
                        all_embeddings.extend([None] * len(sub_batch_texts)) # Append None for failed embeddings
            
            if i + SUB_BATCH_SIZE < len(texts):
                time.sleep(DELAY_BETWEEN_BATCHES_MS / 1000) # Delay between sub-batches
        
        # Filter out None embeddings (failed ones)
        embeddings = [e for e in all_embeddings if e is not None]
        if len(embeddings) != len(texts):
            logger.warning(f"Some embeddings failed. Processed {len(embeddings)} out of {len(texts)} texts.")

        # Upload each chunk with its embedding
        for idx, (node, embedding) in enumerate(zip(nodes, embeddings)):
            self.upload_chunk_with_vector(
                chunk_text=node.get_content(),
                embedding=embedding,
                source_file=str(relative_path),
                chunk_index=idx,
                total_chunks=len(nodes),
                metadata=node.metadata
            )

        # Estimate cost (Titan Embeddings: $0.0001 per 1K tokens)
        if TOKENIZER:
            total_tokens = sum(len(TOKENIZER.encode(text)) for text in texts)
        else:
            total_tokens = sum(len(text.split()) for text in texts) # Fallback to word count
        
        cost = (total_tokens / 1000) * 0.0001
        self.total_cost += cost

    def upload_chunk_with_vector(
        self,
        chunk_text: str,
        embedding: List[float],
        source_file: str,
        chunk_index: int,
        total_chunks: int,
        metadata: Dict
    ):
        """Upload a single chunk with its vector embedding to S3"""

        # Create unique chunk ID using a hash of the relative path
        # This ensures uniqueness even for files with the same name in different directories
        import hashlib
        file_hash = hashlib.sha256(source_file.encode('utf-8')).hexdigest()[:8]
        chunk_id = f"{Path(source_file).stem}_{file_hash}_chunk_{chunk_index:04d}"

        # S3 key for chunk text
        chunk_key = f"chunks/{source_file}/chunk_{chunk_index:04d}.txt"

        # S3 key for vector
        vector_key = f"chunks/{source_file}/chunk_{chunk_index:04d}.vector.json"

        # Metadata for the chunk
        chunk_metadata = {
            'chunk-id': chunk_id,
            'source-file': source_file,
            'chunk-index': str(chunk_index),
            'total-chunks': str(total_chunks),
            'model': self.embeddings.model_id,
            'dimension': str(self.embeddings.dimension)
        }

        try:
            # Upload chunk text
            self.s3.put_object(
                Bucket=BUCKET_NAME,
                Key=chunk_key,
                Body=chunk_text.encode('utf-8'),
                Metadata=chunk_metadata,
                ContentType='text/plain'
            )

            # Upload vector separately (JSON format)
            vector_data = {
                'chunk_id': chunk_id,
                'embedding': embedding,
                'dimension': len(embedding),
                'source_file': source_file,
                'chunk_index': chunk_index
            }

            self.s3.put_object(
                Bucket=BUCKET_NAME,
                Key=vector_key,
                Body=json.dumps(vector_data).encode('utf-8'),
                ContentType='application/json'
            )

            self.uploaded_count += 1

        except Exception as e:
            logger.error(f"Failed to upload chunk {chunk_id}: {e}")


def main():
    print("=" * 70)
    print("GENERATE S3 EMBEDDINGS")
    print("Processing documents and uploading to S3 with vectors")
    print("=" * 70)
    print()
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Region: {REGION}")
    print(f"Chunk size: {CHUNK_SIZE} characters")
    print(f"Overlap: {CHUNK_OVERLAP} characters")
    print(f"Embedding model: {config.BEDROCK_EMBEDDING_MODEL_ID}")
    print()

    # Ask for confirmation
    response = input("This will process ALL documents and upload to S3. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return

    # Process documents
    uploader = S3VectorUploader()
    uploader.process_local_documents("./data")

    print()
    print("=" * 70)
    print("NEXT STEP:")
    print("  Create S3 vector search integration")
    print("  Run: python integrate_s3_vectors.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
