#!/usr/bin/env python3
"""
Migrate chat sessions from filesystem to DynamoDB
"""

import os
import json
import boto3
from datetime import datetime
from pathlib import Path

# Configuration
DYNAMODB_ENDPOINT = "http://localhost:8001"
DYNAMODB_REGION = "us-east-1"
DYNAMODB_TABLE = "smart-tutor-chat-sessions"
USER_DATA_DIR = "user_data"

def get_dynamodb_table():
    """Get DynamoDB table connection"""
    dynamodb = boto3.resource(
        'dynamodb',
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name=DYNAMODB_REGION,
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )
    return dynamodb.Table(DYNAMODB_TABLE)

def load_chat_session(file_path):
    """Load a chat session from JSON file"""
    with open(file_path, 'r') as f:
        return json.load(f)

def migrate_session(table, username, session_id, session_data):
    """Migrate a single session to DynamoDB"""
    # Extract title from filename or use first message
    title = session_data.get('title', session_id.replace('_', ' ').title())

    # Get messages
    messages = session_data.get('messages', [])

    # Ensure messages have proper format
    formatted_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            formatted_messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', datetime.utcnow().isoformat()),
                'sources': msg.get('sources', [])
            })

    # Create DynamoDB item
    item = {
        'user_id': username,
        'session_id': session_id,
        'title': title,
        'messages': formatted_messages,
        'created_at': session_data.get('created_at', datetime.utcnow().isoformat()),
        'updated_at': session_data.get('updated_at', datetime.utcnow().isoformat())
    }

    # Put item in DynamoDB
    table.put_item(Item=item)
    return item

def main():
    """Main migration function"""
    print("=" * 70)
    print("CHAT SESSIONS MIGRATION: Filesystem → DynamoDB")
    print("=" * 70)
    print()

    # Get DynamoDB table
    table = get_dynamodb_table()
    print(f"✓ Connected to DynamoDB table: {DYNAMODB_TABLE}")
    print()

    # Find all users with chat sessions
    user_data_path = Path(USER_DATA_DIR)
    if not user_data_path.exists():
        print(f"✗ User data directory not found: {USER_DATA_DIR}")
        return

    total_migrated = 0
    total_skipped = 0
    total_errors = 0

    # Iterate through users
    for user_dir in user_data_path.iterdir():
        if not user_dir.is_dir():
            continue

        username = user_dir.name.replace('_gmail.com', '@gmail.com')
        chats_dir = user_dir / 'chats'

        if not chats_dir.exists():
            continue

        print(f"Processing user: {username}")
        print("-" * 70)

        # Get all chat session files
        chat_files = list(chats_dir.glob('*.json'))
        print(f"  Found {len(chat_files)} chat session(s)")

        for chat_file in chat_files:
            session_id = chat_file.stem

            try:
                # Check if session already exists in DynamoDB
                response = table.get_item(Key={
                    'user_id': username,
                    'session_id': session_id
                })

                if 'Item' in response:
                    print(f"  ⊘ Skipped: {session_id} (already exists)")
                    total_skipped += 1
                    continue

                # Load and migrate session
                session_data = load_chat_session(chat_file)
                migrated_item = migrate_session(table, username, session_id, session_data)

                message_count = len(migrated_item['messages'])
                print(f"  ✓ Migrated: {session_id} ({message_count} messages)")
                total_migrated += 1

            except Exception as e:
                print(f"  ✗ Error migrating {session_id}: {e}")
                total_errors += 1

        print()

    # Summary
    print("=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"  Migrated: {total_migrated} session(s)")
    print(f"  Skipped:  {total_skipped} session(s) (already existed)")
    print(f"  Errors:   {total_errors} session(s)")
    print()

    if total_migrated > 0:
        print("✓ Migration completed successfully!")
    else:
        print("⚠ No new sessions to migrate")

    # Verify total count in DynamoDB
    print()
    print("Verifying DynamoDB...")
    response = table.scan()
    print(f"  Total sessions in DynamoDB: {response['Count']}")
    print()

if __name__ == "__main__":
    main()
