#!/usr/bin/env python3
import sys
import time
import subprocess
import boto3
from datetime import datetime
from pathlib import Path
import psutil

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(project_root))
from backend.config import config
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError, BotoCoreError

try:
    s3 = boto3.client('s3', region_name=config.AWS_REGION)
except (NoCredentialsError, PartialCredentialsError) as e:
    print(f"Error: AWS credentials not configured. Please set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION. Details: {e}")
    sys.exit(1)
except (ClientError, BotoCoreError) as e:
    print(f"Error initializing S3 client in region {config.AWS_REGION}: {e}")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred during S3 client initialization: {e}")
    sys.exit(1)

def get_chunk_count():
    paginator = s3.get_paginator('list_objects_v2')
    count = 0
    for page in paginator.paginate(Bucket=config.S3_DOCUMENTS_BUCKET, Prefix='chunks/modules/'):
        if 'Contents' in page:
            count += sum(1 for obj in page['Contents'] if obj['Key'].endswith('.txt'))
    return count

def is_process_running(process_name: str = 'process_all_missing.py') -> bool:
    """
    Checks if a process with the given name or command line argument is running.
    Uses psutil for cross-platform compatibility.
    """
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            # Check by process name
            if proc.info['name'] == process_name:
                return True
            # Check by command line arguments
            if proc.info['cmdline'] and process_name in ' '.join(proc.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Process no longer exists, access denied, or zombie process
            continue
        except Exception as e:
            print(f"Error checking process: {e}")
            continue
    return False

print("=" * 70)
print("MONITORING DOCUMENT PROCESSING")
print("=" * 70)
print()

start_count = get_chunk_count()
start_time = datetime.now()

print(f"Start time: {start_time.strftime('%H:%M:%S')}")
print(f"Initial chunks: {start_count}")
print()
print("Monitoring every 5 minutes... (Press Ctrl+C to stop)")
print()

try:
    while True:
        if not is_process_running('process_all_missing.py'):
            print("\n" + "=" * 70)
            print("PROCESSING COMPLETE!")
            print("=" * 70)
            
            final_count = get_chunk_count()
            elapsed = datetime.now() - start_time
            
            print(f"Final chunks: {final_count}")
            print(f"New chunks: {final_count - start_count}")
            print(f"Time elapsed: {elapsed}")
            print()
            print("✅ Ready to rebuild vector index!")
            break
        
        current_count = get_chunk_count()
        new_chunks = current_count - start_count
        elapsed = datetime.now() - start_time
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Chunks: {current_count} (+{new_chunks}) | Elapsed: {str(elapsed).split('.')[0]}")
        
        time.sleep(300)  # Check every 5 minutes
        
except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user")
    current_count = get_chunk_count()
    print(f"Current chunks: {current_count} (+{current_count - start_count})")
