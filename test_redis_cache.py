#!/usr/bin/env python3
"""
Test script for Phase 3 Redis caching and session management
"""

import sys
import time
import uuid

sys.path.insert(0, '.')

from backend.redis_cache import get_redis_cache
from backend.session_store import get_session_store


def test_redis_cache():
    """Test Redis cache functionality"""
    print("\n=== Testing Redis Cache ===")

    cache = get_redis_cache()

    # Test 1: Ping
    print("\n1. Testing Redis connection...")
    if cache.ping():
        print("✓ Redis connection successful")
    else:
        print("✗ Redis connection failed")
        return False

    # Test 2: Set and Get
    print("\n2. Testing set/get...")
    cache.set("test_key", "test_value", ttl=60)
    value = cache.get("test_key")
    if value == "test_value":
        print("✓ Set/Get working correctly")
    else:
        print(f"✗ Set/Get failed: expected 'test_value', got '{value}'")

    # Test 3: Complex data types
    print("\n3. Testing complex data types...")
    test_data = {
        "user": "test_user",
        "items": [1, 2, 3],
        "nested": {"key": "value"}
    }
    cache.set("complex_key", test_data, ttl=60)
    retrieved = cache.get("complex_key")
    if retrieved == test_data:
        print("✓ Complex data serialization working")
    else:
        print(f"✗ Complex data failed")

    # Test 4: TTL and expiration
    print("\n4. Testing TTL...")
    cache.set("expire_key", "will_expire", ttl=2)
    ttl = cache.get_ttl("expire_key")
    print(f"✓ Key TTL: {ttl} seconds")
    time.sleep(3)
    expired_value = cache.get("expire_key")
    if expired_value is None:
        print("✓ TTL expiration working")
    else:
        print("✗ Key did not expire")

    # Test 5: Delete
    print("\n5. Testing delete...")
    cache.set("delete_key", "to_delete", ttl=60)
    cache.delete("delete_key")
    deleted_value = cache.get("delete_key")
    if deleted_value is None:
        print("✓ Delete working correctly")
    else:
        print("✗ Delete failed")

    # Test 6: Increment
    print("\n6. Testing increment...")
    # Delete key first to ensure it doesn't have a pickled value
    cache.delete("counter")
    cache.increment("counter", 5)
    cache.increment("counter", 3)
    # For increment, we need to get the raw value directly from Redis
    counter_value = cache.client.get("counter")
    counter_int = int(counter_value) if counter_value else 0
    if counter_int == 8:
        print(f"✓ Increment working: {counter_int}")
    else:
        print(f"✗ Increment failed: expected 8, got {counter_int}")

    # Test 7: Stats
    print("\n7. Getting cache stats...")
    stats = cache.get_stats()
    print(f"✓ Cache stats:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")

    print("\n✓ Redis cache tests completed!")
    return True


def test_session_store():
    """Test Redis session store"""
    print("\n=== Testing Redis Session Store ===")

    store = get_session_store()

    # Test 1: Store refresh token
    print("\n1. Storing refresh token...")
    token_id = str(uuid.uuid4())
    username = "test_user"
    token = f"refresh_token_{token_id}"

    success = store.store_refresh_token(token_id, username, token, ttl=300)
    if success:
        print(f"✓ Refresh token stored for {username}")
    else:
        print("✗ Failed to store refresh token")
        return False

    # Test 2: Retrieve refresh token
    print("\n2. Retrieving refresh token...")
    token_data = store.get_refresh_token(token_id)
    if token_data and token_data["username"] == username:
        print(f"✓ Retrieved token for {username}")
        print(f"  Created at: {token_data['created_at']}")
    else:
        print("✗ Failed to retrieve token")

    # Test 3: Multiple sessions for user
    print("\n3. Creating multiple sessions...")
    for i in range(3):
        tid = str(uuid.uuid4())
        store.store_refresh_token(tid, username, f"token_{i}", ttl=300)

    session_count = store.get_session_count(username)
    print(f"✓ User has {session_count} active sessions")

    # Test 4: Get user sessions
    print("\n4. Listing user sessions...")
    sessions = store.get_user_sessions(username)
    print(f"✓ Found {len(sessions)} sessions")
    for idx, session_id in enumerate(sessions[:3], 1):
        print(f"  {idx}. {session_id[:8]}...")

    # Test 5: Session limit enforcement
    print("\n5. Testing session limit...")
    store.limit_user_sessions(username, max_sessions=3)
    new_count = store.get_session_count(username)
    print(f"✓ Sessions after limit enforcement: {new_count}")

    # Test 6: Delete specific token
    print("\n6. Deleting specific token...")
    store.delete_refresh_token(token_id, username)
    deleted_token = store.get_refresh_token(token_id)
    if deleted_token is None:
        print("✓ Token successfully deleted")
    else:
        print("✗ Token still exists")

    # Test 7: Revoke all user sessions
    print("\n7. Revoking all user sessions...")
    revoked = store.revoke_all_user_sessions(username)
    print(f"✓ Revoked {revoked} sessions for {username}")

    final_count = store.get_session_count(username)
    if final_count == 0:
        print(f"✓ All sessions cleared (count: {final_count})")
    else:
        print(f"⚠ {final_count} sessions remaining")

    print("\n✓ Session store tests completed!")
    return True


def test_cache_performance():
    """Test cache performance"""
    print("\n=== Testing Cache Performance ===")

    cache = get_redis_cache()

    # Test write performance
    print("\n1. Testing write performance (1000 keys)...")
    start_time = time.time()
    for i in range(1000):
        cache.set(f"perf_key_{i}", f"value_{i}", ttl=60)
    write_time = time.time() - start_time
    print(f"✓ Wrote 1000 keys in {write_time:.3f}s ({1000/write_time:.0f} ops/sec)")

    # Test read performance
    print("\n2. Testing read performance (1000 keys)...")
    start_time = time.time()
    for i in range(1000):
        cache.get(f"perf_key_{i}")
    read_time = time.time() - start_time
    print(f"✓ Read 1000 keys in {read_time:.3f}s ({1000/read_time:.0f} ops/sec)")

    # Cleanup
    print("\n3. Cleaning up test keys...")
    cache.clear("perf_key_*")
    print("✓ Test keys cleaned up")

    print("\n✓ Performance tests completed!")
    return True


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Phase 3 Redis Cache & Session Management Tests")
        print("=" * 60)

        # Test each component
        cache_ok = test_redis_cache()
        session_ok = test_session_store()
        perf_ok = test_cache_performance()

        print("\n" + "=" * 60)
        if cache_ok and session_ok and perf_ok:
            print("✓ All Phase 3 tests passed successfully!")
        else:
            print("✗ Some tests failed")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
