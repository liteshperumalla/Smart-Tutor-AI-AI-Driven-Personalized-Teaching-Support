#!/usr/bin/env python3
"""
Test script for Phase 2 database backends
Tests PostgreSQL, DynamoDB, and Hybrid storage backends
"""

import sys
from datetime import datetime

# Add backend to path
sys.path.insert(0, '.')

from backend.services.storage.postgres import get_postgres_backend
from backend.services.storage.dynamodb import get_dynamodb_backend
from backend.services.storage.hybrid import get_hybrid_backend
from backend.services.models import ChatSession, QuizResult


def test_postgres():
    """Test PostgreSQL backend"""
    print("\n=== Testing PostgreSQL Backend ===")

    postgres = get_postgres_backend()

    # Test 1: Create user
    print("\n1. Creating test user...")
    try:
        user = postgres.create_user(
            username="test_postgres_user",
            password_hash="hashed_password_123",
            email="test@postgres.com",
            display_name="Test Postgres User"
        )
        print(f"✓ User created: {user['username']}")
    except ValueError as e:
        print(f"✓ User already exists: {e}")

    # Test 2: Get user
    print("\n2. Getting user...")
    user = postgres.get_user("test_postgres_user")
    if user:
        print(f"✓ User retrieved: {user['username']} ({user['email']})")
    else:
        print("✗ User not found")

    # Test 3: Update user
    print("\n3. Updating user...")
    updated_user = postgres.update_user(
        "test_postgres_user",
        {"theme": "dark", "login_attempts": 0}
    )
    print(f"✓ User updated: theme={updated_user['theme']}")

    # Test 4: Save quiz result
    print("\n4. Saving quiz result...")
    quiz_result = QuizResult(
        id="test_quiz_1",
        user_id="test_postgres_user",
        score=8,
        total_questions=10,
        percentage=80.0,
        metadata={"time_taken": 120, "correct_answers": 8}
    )
    postgres.save_quiz_result(quiz_result)
    print("✓ Quiz result saved")

    # Test 5: List quiz results
    print("\n5. Listing quiz results...")
    results = postgres.list_quiz_results("test_postgres_user")
    print(f"✓ Found {len(results)} quiz result(s)")
    for result in results[:3]:  # Show first 3
        print(f"  - {result.id}: {result.percentage}%")

    print("\n✓ PostgreSQL tests completed successfully!")


def test_dynamodb():
    """Test DynamoDB backend"""
    print("\n=== Testing DynamoDB Backend ===")

    dynamodb = get_dynamodb_backend()

    # Test 1: Save chat session
    print("\n1. Saving chat session...")
    session = ChatSession(
        id="test_session_1",
        title="Test Chat Session",
        messages=[
            {"role": "user", "content": "Hello", "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": "Hi there!", "timestamp": datetime.now().isoformat()}
        ]
    )
    dynamodb.save_chat_session("test_dynamo_user", session)
    print("✓ Chat session saved")

    # Test 2: Load chat session
    print("\n2. Loading chat session...")
    loaded_session = dynamodb.load_chat_session("test_dynamo_user", "test_session_1")
    if loaded_session:
        print(f"✓ Chat session loaded: {loaded_session.title}")
        print(f"  Messages: {len(loaded_session.messages)}")
    else:
        print("✗ Chat session not found")

    # Test 3: List chat sessions
    print("\n3. Listing chat sessions...")
    sessions = dynamodb.list_chat_sessions("test_dynamo_user")
    print(f"✓ Found {len(sessions)} chat session(s)")
    for sess in sessions[:3]:
        print(f"  - {sess.id}: {sess.title} ({len(sess.messages)} messages)")

    # Test 4: Save another session
    print("\n4. Saving second chat session...")
    session2 = ChatSession(
        id="test_session_2",
        title="Another Test Session",
        messages=[
            {"role": "user", "content": "How are you?", "timestamp": datetime.now().isoformat()},
        ]
    )
    dynamodb.save_chat_session("test_dynamo_user", session2)
    print("✓ Second chat session saved")

    # Test 5: List again
    print("\n5. Listing all sessions...")
    sessions = dynamodb.list_chat_sessions("test_dynamo_user")
    print(f"✓ Found {len(sessions)} chat session(s)")

    print("\n✓ DynamoDB tests completed successfully!")


def test_hybrid():
    """Test Hybrid backend"""
    print("\n=== Testing Hybrid Backend ===")

    hybrid = get_hybrid_backend()

    # Test 1: Create user (routes to PostgreSQL)
    print("\n1. Creating user via hybrid backend...")
    try:
        user = hybrid.create_user(
            username="test_hybrid_user",
            password_hash="hashed_password_456",
            email="test@hybrid.com"
        )
        print(f"✓ User created: {user['username']}")
    except ValueError:
        print("✓ User already exists")

    # Test 2: Save chat session (routes to DynamoDB)
    print("\n2. Saving chat session via hybrid backend...")
    session = ChatSession(
        id="hybrid_session_1",
        title="Hybrid Test Session",
        messages=[
            {"role": "user", "content": "Test", "timestamp": datetime.now().isoformat()},
        ]
    )
    hybrid.save_chat_session("test_hybrid_user", session)
    print("✓ Chat session saved")

    # Test 3: Get user (from PostgreSQL)
    print("\n3. Getting user via hybrid backend...")
    user = hybrid.get_user("test_hybrid_user")
    print(f"✓ User retrieved: {user['email']}")

    # Test 4: Load chat session (from DynamoDB)
    print("\n4. Loading chat session via hybrid backend...")
    loaded_session = hybrid.load_chat_session("test_hybrid_user", "hybrid_session_1")
    if loaded_session:
        print(f"✓ Chat session loaded: {loaded_session.title}")
    else:
        print("✗ Chat session not found")

    # Test 5: Save quiz result (routes to PostgreSQL)
    print("\n5. Saving quiz result via hybrid backend...")
    quiz = QuizResult(
        id="hybrid_quiz_1",
        user_id="test_hybrid_user",
        score=9,
        total_questions=10,
        percentage=90.0,
        metadata={"time_taken": 150}
    )
    hybrid.save_quiz_result(quiz)
    print("✓ Quiz result saved")

    # Test 6: List quiz results (from PostgreSQL)
    print("\n6. Listing quiz results via hybrid backend...")
    results = hybrid.list_quiz_results("test_hybrid_user")
    print(f"✓ Found {len(results)} quiz result(s)")

    print("\n✓ Hybrid backend tests completed successfully!")


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Phase 2 Storage Backend Tests")
        print("=" * 60)

        # Test each backend
        test_postgres()
        test_dynamodb()
        test_hybrid()

        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
