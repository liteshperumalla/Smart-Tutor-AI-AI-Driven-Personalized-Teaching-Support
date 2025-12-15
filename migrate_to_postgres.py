#!/usr/bin/env python3
"""
Migration Script: JSON to PostgreSQL
Migrates existing users from users.json to PostgreSQL database
"""

import sys
import json

sys.path.insert(0, '.')

from backend.services.storage.postgres import get_postgres_backend
from backend.logger import get_logger

logger = get_logger(__name__)


def migrate_users():
    """Migrate users from JSON file to PostgreSQL"""
    print("=" * 60)
    print("User Migration: JSON → PostgreSQL")
    print("=" * 60)

    # Load existing users from JSON
    print("\n1. Loading users from users.json...")
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)

        print(f"✓ Found {len(users_data)} users in JSON file")
    except FileNotFoundError:
        print("✗ users.json not found")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ Error parsing users.json: {e}")
        return False

    # Connect to PostgreSQL
    print("\n2. Connecting to PostgreSQL...")
    try:
        postgres = get_postgres_backend()
        print("✓ PostgreSQL connection established")
    except Exception as e:
        print(f"✗ Failed to connect to PostgreSQL: {e}")
        return False

    # Migrate each user
    print("\n3. Migrating users...")
    migrated = 0
    skipped = 0
    errors = 0

    for username, user_data in users_data.items():
        try:
            # Check if user already exists
            existing = postgres.get_user(username)
            if existing:
                print(f"  ⊙ {username} - already exists in PostgreSQL")
                skipped += 1
                continue

            # Create user in PostgreSQL
            postgres.create_user(
                username=username,
                password_hash=user_data.get('hashed_password', ''),
                email=user_data.get('email', username),
                display_name=user_data.get('display_name', username),
                phone_number=user_data.get('phone_number', ''),
                role=user_data.get('role', 'User'),
                theme=user_data.get('theme', 'light'),
                notes=user_data.get('notes', ''),
                profile_picture_path=user_data.get('profile_picture_path', '')
            )

            # Update additional fields if present
            updates = {}
            if 'login_attempts' in user_data:
                updates['login_attempts'] = user_data['login_attempts']
            if 'locked_until' in user_data:
                updates['locked_until'] = user_data['locked_until']
            if 'last_login' in user_data:
                updates['last_login'] = user_data['last_login']

            if updates:
                postgres.update_user(username, updates)

            print(f"  ✓ {username} - migrated successfully")
            migrated += 1

        except Exception as e:
            print(f"  ✗ {username} - error: {e}")
            errors += 1

    # Summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Total users in JSON: {len(users_data)}")
    print(f"Successfully migrated: {migrated}")
    print(f"Already existed (skipped): {skipped}")
    print(f"Errors: {errors}")
    print("=" * 60)

    if errors > 0:
        print("\n⚠ Some users failed to migrate. Check errors above.")
        return False
    else:
        print("\n✓ Migration completed successfully!")
        return True


def verify_migration():
    """Verify migration was successful"""
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)

    # Load JSON users
    with open('users.json', 'r') as f:
        json_users = json.load(f)

    # Check PostgreSQL
    postgres = get_postgres_backend()

    print(f"\nChecking {len(json_users)} users...")
    all_found = True

    for username in json_users.keys():
        pg_user = postgres.get_user(username)
        if pg_user:
            print(f"  ✓ {username} - found in PostgreSQL")
        else:
            print(f"  ✗ {username} - NOT found in PostgreSQL")
            all_found = False

    if all_found:
        print("\n✓ All users successfully migrated!")
    else:
        print("\n✗ Some users are missing in PostgreSQL")

    return all_found


if __name__ == "__main__":
    try:
        # Run migration
        success = migrate_users()

        if success:
            # Verify
            verify_migration()
            print("\n" + "=" * 60)
            print("✓ Ready to activate production configuration!")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n✗ Migration failed")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
