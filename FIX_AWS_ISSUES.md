# Fix AWS Issues - Step-by-Step Guide

**Date:** December 18, 2025
**Status:** Ready to Execute

---

## Issues Identified

From the AWS Test Report, we need to fix:

1. ✅ **FIXED:** Bedrock token counting (updated `bedrock_llm.py`)
2. ⚠️ **ACTION REQUIRED:** DynamoDB permissions and table creation

---

## Issue 1: Bedrock Token Counting ✅ FIXED

**Problem:** Token counts showing as 0 in get_stats()

**Solution:** Updated `backend/bedrock_llm.py` to track tokens in Llama generation

**Changes Made:**
```python
# Added token tracking in _generate_llama method (lines 200-203)
self.total_input_tokens += input_tokens
self.total_output_tokens += output_tokens
self.total_cost += cost
```

**Verification:**
```bash
source venv/bin/activate
python3 << 'EOF'
from backend.bedrock_llm import BedrockLLM
llm = BedrockLLM(model_id="meta.llama3-70b-instruct-v1:0", region="us-east-1")
response = llm.generate("Test", max_tokens=50)
stats = llm.get_stats()
print(f"Stats: {stats}")
EOF
```

**Status:** ✅ COMPLETE - No action needed

---

## Issue 2: DynamoDB Access ⚠️ ACTION REQUIRED

**Problem:** IAM user `smart-tutor` lacks DynamoDB permissions

**Error:**
```
AccessDeniedException: User: arn:aws:iam::183631304219:user/smart-tutor
is not authorized to perform: dynamodb:ListTables
```

### Step 1: Grant IAM Permissions

You need to attach the DynamoDB policy to your IAM user. Choose ONE method:

#### Method A: AWS Console (Recommended - Easy)

1. **Login to AWS Console:** https://console.aws.amazon.com/

2. **Navigate to IAM:**
   - Services → IAM → Users → smart-tutor

3. **Add Permissions:**
   - Click "Add permissions" button
   - Click "Create inline policy"

4. **Paste Policy:**
   - Switch to JSON tab
   - Paste the contents of `/tmp/dynamodb-iam-policy.json`
   - Policy name: `SmartTutorDynamoDBAccess`
   - Click "Create policy"

5. **Verify:**
   - You should see the new policy listed under the user's permissions

#### Method B: AWS CLI (If you have admin access)

```bash
aws iam put-user-policy \
  --user-name smart-tutor \
  --policy-name SmartTutorDynamoDBAccess \
  --policy-document file:///tmp/dynamodb-iam-policy.json
```

#### Method C: AWS CloudShell (In Browser)

1. Open AWS Console
2. Click the CloudShell icon (terminal icon in top navigation)
3. Upload the policy file from `/tmp/dynamodb-iam-policy.json`
4. Run the command from Method B

### Step 2: Create DynamoDB Tables

Once permissions are granted, create the three required tables:

#### Method A: AWS Console (Visual)

1. **Navigate to DynamoDB:**
   - Services → DynamoDB → Tables → Create table

2. **Create Table 1: Chat Sessions**
   - Table name: `smart-tutor-chat-sessions`
   - Partition key: `user_id` (String)
   - Sort key: `session_id` (String)
   - Table settings: Default settings
   - Read/write capacity: On-demand
   - Tags:
     - Key: `Application`, Value: `smart-ai-tutor`
     - Key: `Environment`, Value: `production`
   - Click "Create table"

3. **Create Table 2: Users**
   - Table name: `smart-tutor-users`
   - Partition key: `username` (String)
   - No sort key
   - Table settings: Default settings
   - Read/write capacity: On-demand
   - Tags: Same as above
   - Click "Create table"

4. **Create Table 3: Quiz Results**
   - Table name: `smart-tutor-quiz-results`
   - Partition key: `username` (String)
   - Sort key: `quiz_id` (String)
   - Table settings: Default settings
   - Read/write capacity: On-demand
   - Tags: Same as above
   - Click "Create table"

#### Method B: Using Setup Script (Automated)

```bash
./setup_aws_dynamodb.sh
```

This script will create all three tables automatically once you have permissions.

#### Method C: AWS CLI (Manual Commands)

```bash
# Table 1: Chat Sessions
aws dynamodb create-table \
  --table-name smart-tutor-chat-sessions \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=session_id,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=session_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1 \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production

# Table 2: Users
aws dynamodb create-table \
  --table-name smart-tutor-users \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1 \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production

# Table 3: Quiz Results
aws dynamodb create-table \
  --table-name smart-tutor-quiz-results \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
    AttributeName=quiz_id,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
    AttributeName=quiz_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1 \
  --tags Key=Application,Value=smart-ai-tutor Key=Environment,Value=production
```

### Step 3: Verify Table Creation

Wait for tables to become ACTIVE (usually 1-2 minutes), then verify:

```bash
source venv/bin/activate
python3 << 'EOF'
import boto3

dynamodb = boto3.client('dynamodb', region_name='us-east-1')
response = dynamodb.list_tables()

smart_tutor_tables = [t for t in response['TableNames'] if 'smart-tutor' in t]
print(f"✅ Smart Tutor tables: {len(smart_tutor_tables)}")
for table in smart_tutor_tables:
    info = dynamodb.describe_table(TableName=table)
    status = info['Table']['TableStatus']
    print(f"  - {table}: {status}")
EOF
```

Expected output:
```
✅ Smart Tutor tables: 3
  - smart-tutor-chat-sessions: ACTIVE
  - smart-tutor-quiz-results: ACTIVE
  - smart-tutor-users: ACTIVE
```

### Step 4: Switch to DynamoDB Storage

Once tables are created and ACTIVE:

1. **Update .env:**
   ```bash
   # Change from filesystem to dynamodb
   STORAGE_BACKEND=dynamodb
   ```

2. **Restart backend:**
   ```bash
   ./manage_services.sh restart backend
   ```

3. **Verify:**
   ```bash
   tail -f logs/backend_api.log | grep -i dynamodb
   ```

   You should see:
   ```
   DynamoDB storage backend initialized
   ```

---

## Testing After Fixes

Run the complete test suite again:

```bash
source venv/bin/activate
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

print("Testing AWS Stack After Fixes...")
print("=" * 70)

# Test 1: Bedrock token counting
print("\n1. Testing Bedrock Token Counting...")
from backend.bedrock_llm import BedrockLLM
llm = BedrockLLM(model_id="meta.llama3-70b-instruct-v1:0", region="us-east-1")
response = llm.generate("What is AI?", max_tokens=50)
stats = llm.get_stats()
assert stats['total_input_tokens'] > 0, "Input tokens should be > 0"
assert stats['total_output_tokens'] > 0, "Output tokens should be > 0"
print(f"   ✅ Token counting works: {stats}")

# Test 2: DynamoDB access
print("\n2. Testing DynamoDB Access...")
import boto3
dynamodb = boto3.client('dynamodb', region_name='us-east-1')
tables = dynamodb.list_tables()
smart_tutor_tables = [t for t in tables['TableNames'] if 'smart-tutor' in t]
assert len(smart_tutor_tables) >= 3, "Should have at least 3 smart-tutor tables"
print(f"   ✅ DynamoDB access works: {len(smart_tutor_tables)} tables found")

# Test 3: DynamoDB storage backend
print("\n3. Testing DynamoDB Storage Backend...")
from backend.services.storage.dynamodb import DynamoDBStorageBackend
backend = DynamoDBStorageBackend(region_name='us-east-1', table_name='smart-tutor-chat-sessions')
sessions = backend.list_chat_sessions("test-user")
print(f"   ✅ DynamoDB backend works: {len(sessions)} sessions for test-user")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
EOF
```

---

## Summary Checklist

### Pre-requisites
- [x] Bedrock token counting fixed in code
- [x] IAM policy JSON created
- [ ] IAM policy attached to smart-tutor user
- [ ] DynamoDB tables created

### Execution Steps
1. [ ] Attach IAM policy (see Step 1 above)
2. [ ] Create DynamoDB tables (see Step 2 above)
3. [ ] Verify tables are ACTIVE (see Step 3 above)
4. [ ] Update .env: `STORAGE_BACKEND=dynamodb`
5. [ ] Restart backend
6. [ ] Run verification tests
7. [ ] Test in UI

### Expected Results
- ✅ All AWS services operational
- ✅ Token counting accurate
- ✅ DynamoDB storing chat sessions
- ✅ Cost tracking to S3 working
- ✅ 100% AWS infrastructure (no local dependencies)

---

## Cost Impact

### Current State (Filesystem Storage)
- Bedrock LLM: $0.00265/1K input, $0.0035/1K output
- Bedrock Embeddings: $0.00002/1K tokens
- S3 Storage: ~$0.53/mo
- **Total: ~$0.53/mo + usage**

### After DynamoDB Migration
- Add DynamoDB: ~$5-25/mo (PAY_PER_REQUEST)
- **Total: ~$5.53-25.53/mo + Bedrock usage**

### Bedrock Usage Costs
- Light (100 queries/day): ~$54/mo
- Medium (1,000 queries/day): ~$540/mo
- Heavy (10,000 queries/day): ~$5,400/mo

**Total Monthly (Medium usage): ~$546-566/mo**

---

## Support

If you encounter issues:

1. **Check logs:**
   ```bash
   tail -f logs/backend_api.log
   ```

2. **Verify AWS credentials:**
   ```bash
   aws sts get-caller-identity
   ```

3. **Check DynamoDB tables:**
   ```bash
   aws dynamodb list-tables --region us-east-1
   ```

4. **Test individual components:**
   - Run the verification script above
   - Check AWS Console for error messages
   - Review IAM policies

---

**Last Updated:** December 18, 2025
**Status:** Ready for execution
**Priority:** HIGH - Required for full AWS migration
