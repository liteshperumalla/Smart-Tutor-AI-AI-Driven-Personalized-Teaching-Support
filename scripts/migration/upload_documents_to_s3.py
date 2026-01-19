#!/usr/bin/env python3
"""
Upload original course documents to S3 for viewing/downloading.
These are the actual PDF, PPTX, DOCX files that users can click to view.
"""

import os
import sys
from pathlib import Path
import boto3
from botocore.config import Config

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import config

# Configuration
S3_BUCKET = "smart-ai-tutor-docs"
S3_PREFIX = "modules/"  # Files will be at smart-ai-tutor-docs/modules/...
MODULES_DIR = "./Modules"

# Configure S3 client
s3_config = Config(signature_version="s3v4", region_name="us-east-1")
s3_client = boto3.client("s3", config=s3_config, region_name="us-east-1")

# File extensions to upload
SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".ipynb"}


def get_content_type(file_path: str) -> str:
    """Get the content type for a file based on extension."""
    ext = Path(file_path).suffix.lower()
    content_types = {
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".ipynb": "application/x-ipynb+json",
    }
    return content_types.get(ext, "application/octet-stream")


def upload_document(file_path: str, s3_key: str) -> bool:
    """Upload a single document to S3."""
    try:
        content_type = get_content_type(file_path)
        with open(file_path, "rb") as f:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=f.read(),
                ContentType=content_type,
                Metadata={
                    "original_path": file_path,
                    "uploaded_by": "upload_documents_to_s3.py",
                },
            )
        print(f"  ✅ Uploaded: {s3_key}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {s3_key} - {e}")
        return False


def main():
    """Main function to upload all documents."""
    modules_path = Path(MODULES_DIR)

    if not modules_path.exists():
        print(f"❌ Error: Modules directory not found: {MODULES_DIR}")
        sys.exit(1)

    print(f"📁 Scanning for documents in: {MODULES_DIR}")
    print(f"🪣 Uploading to: s3://{S3_BUCKET}/{S3_PREFIX}")
    print("-" * 60)

    uploaded_count = 0
    skipped_count = 0

    for root, dirs, files in os.walk(modules_path):
        for filename in files:
            ext = Path(filename).suffix.lower()

            if ext not in SUPPORTED_EXTENSIONS:
                continue

            # Get relative path from modules directory
            file_path = Path(root) / filename
            rel_path = file_path.relative_to(modules_path)

            # Create S3 key: modules/Module X/filename.pdf
            s3_key = f"{S3_PREFIX}{rel_path}"

            # Check if file already exists in S3
            try:
                s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
                print(f"  ⏭️  Skipped (exists): {s3_key}")
                skipped_count += 1
            except s3_client.exceptions.NoSuchKey:
                # File doesn't exist, upload it
                if upload_document(str(file_path), s3_key):
                    uploaded_count += 1

    print("-" * 60)
    print(f"✅ Upload complete!")
    print(f"   Uploaded: {uploaded_count} files")
    print(f"   Skipped:  {skipped_count} files")
    print(f"\n📂 S3 location: s3://{S3_BUCKET}/{S3_PREFIX}")


if __name__ == "__main__":
    main()
