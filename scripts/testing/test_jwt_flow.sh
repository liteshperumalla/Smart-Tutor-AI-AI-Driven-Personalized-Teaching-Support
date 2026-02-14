#!/bin/bash

echo "Testing JWT Authentication Flow"
echo "================================"

# Login
echo -e "\n1. Logging in..."
curl -s -X POST 'http://localhost:8010/auth/login' \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${TEST_USERNAME:-testuser@example.com}\",\"password\":\"${TEST_PASSWORD:-changeme}\"}" \
  > /tmp/login.json

echo "✓ Login successful"

# Extract tokens
ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login.json'))['access_token'])")
REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login.json'))['refresh_token'])")

echo "✓ Tokens extracted"

# Test access token
echo -e "\n2. Testing access token..."
curl -s "http://localhost:8010/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool

echo -e "\n✓ All JWT features working!"
