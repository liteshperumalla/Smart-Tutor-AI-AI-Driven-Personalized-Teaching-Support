# Phase 4: AWS Bedrock Migration - Implementation Plan

**Date:** December 16, 2025
**Status:** 🚀 **IN PROGRESS**
**Previous Phases:** Phase 1-3 Complete (Security, Database, Caching)

---

## 📋 Overview

Phase 4 migrates the AI/LLM infrastructure from local Ollama to AWS Bedrock, enabling:
- Production-grade LLM inference (Claude 3.5 Sonnet / Llama 3.1)
- Managed embeddings (Amazon Titan Text Embeddings v2)
- Scalable vector storage (Bedrock Knowledge Base or pgvector)
- Cost tracking and optimization
- Enterprise security and compliance

---

## 🎯 Goals

### Primary Objectives
1. ✅ Replace Ollama with AWS Bedrock for LLM inference
2. ✅ Migrate embeddings to Amazon Titan or Bedrock models
3. ✅ Set up S3 for document storage with versioning
4. ✅ Configure Bedrock Knowledge Base with hierarchical chunking
5. ✅ Implement cost tracking per query
6. ✅ Maintain backward compatibility with local development

### Success Metrics
- LLM response time < 3 seconds (95th percentile)
- Embedding generation < 500ms per batch
- Vector search < 200ms
- Cost per query < $0.01
- Zero downtime migration

---

## 🏗️ Architecture Changes

### Before (Current)
```
User Query
    ↓
Tutor_chat.py (RAG Engine)
    ↓
LlamaIndex + ChromaDB (Vector Store)
    ↓
Ollama (llama3.2) - Local LLM
    ↓
HuggingFace (BAAI/bge-small-en-v1.5) - Local Embeddings
    ↓
Response
```

### After (Phase 4)
```
User Query
    ↓
FastAPI Backend
    ↓
Bedrock Adapter (LLM Abstraction)
    ├── AWS Bedrock (Claude 3.5 Sonnet)
    └── Ollama (Local fallback - dev only)
    ↓
Bedrock Knowledge Base
    ├── Amazon Titan Embeddings v2 (1024-dim)
    ├── S3 Document Storage (versioned)
    └── OpenSearch Serverless (Vector Store)
    ↓
Response + Cost Tracking
```

---

## 📊 Implementation Tasks

### 1. AWS Infrastructure Setup

#### 1.1 Enable AWS Bedrock Access
```bash
# Region: us-east-1 (primary) or us-east-2
# Models to enable:
# - anthropic.claude-3-5-sonnet-20241022-v2:0 (LLM)
# - amazon.titan-embed-text-v2:0 (Embeddings)
# - meta.llama3-1-70b-instruct-v1:0 (Alternative LLM)

aws bedrock list-foundation-models --region us-east-1
aws bedrock get-model-access --region us-east-1
```

**Status:** ⏸️ Pending
**Owner:** DevOps/Admin
**Blockers:** AWS account setup, billing enabled

#### 1.2 Create S3 Buckets
```bash
# Document storage bucket
aws s3 mb s3://smart-ai-tutor-docs --region us-east-1

# User uploads bucket
aws s3 mb s3://smart-ai-tutor-uploads --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket smart-ai-tutor-docs \
  --versioning-configuration Status=Enabled

# Lifecycle policy (delete old versions after 90 days)
# NOTE: s3-lifecycle.json is not included in this document.
# Create a file named s3-lifecycle.json with the following content:
# {
#   "Rules": [
#     {
#       "ID": "DeleteOldVersions",
#       "Status": "Enabled",
#       "Filter": { "Prefix": "" },
#       "NoncurrentVersionExpiration": { "NoncurrentDays": 90 }
#     }
#   ]
# }
aws s3api put-bucket-lifecycle-configuration \
  --bucket smart-ai-tutor-docs \
  --lifecycle-configuration file://s3-lifecycle.json
```

**Status:** ⏸️ Pending
**Dependencies:** AWS account, IAM permissions

#### 1.3 IAM Role Configuration
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-*",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-*"
      ]
    },
    {
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": [
            "arn:aws:s3:::smart-ai-tutor-docs",
            "arn:aws:s3:::smart-ai-tutor-uploads"
        ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::smart-ai-tutor-docs/*",
        "arn:aws:s3:::smart-ai-tutor-uploads/*"
      ]
    }
  ]
}
```

**Status:** ⏸️ Pending
**File:** `aws/iam-bedrock-role.json`

---

### 2. Bedrock Knowledge Base Setup

#### 2.1 Knowledge Base Configuration
```python
# Hierarchical Chunking Strategy
PARENT_CHUNK_SIZE = 1024  # tokens
PARENT_CHUNK_OVERLAP = 200  # tokens (20%)
CHILD_CHUNK_SIZE = 256  # tokens
CHILD_CHUNK_OVERLAP = 50  # tokens (20%)

# Embedding Model
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024  # dimensions

# Vector Store
VECTOR_STORE = "OpenSearch Serverless"  # or pgvector
```

#### 2.2 Document Upload to S3
```bash
# Upload course materials
aws s3 sync ./Modules/ s3://smart-ai-tutor-docs/modules/ \
  --exclude "*.pyc" --exclude "__pycache__/*"

# Upload data files
aws s3 sync ./data/ s3://smart-ai-tutor-docs/data/
```

**Status:** ⏸️ Pending
**Dependencies:** S3 buckets created

#### 2.3 Create Bedrock Knowledge Base
```bash
# Via AWS Console or CLI
aws bedrock-agent create-knowledge-base \
  --name smart-ai-tutor-kb \
  --role-arn arn:aws:iam::ACCOUNT:role/BedrockKBRole \
  --knowledge-base-configuration '{
    "type": "VECTOR",
    "vectorKnowledgeBaseConfiguration": {
      "embeddingModelArn": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
    }
  }' \
  --storage-configuration '{
    "type": "OPENSEARCH_SERVERLESS",
    "opensearchServerlessConfiguration": {
      "collectionArn": "arn:aws:aoss:us-east-1:ACCOUNT:collection/xyz",
      "vectorIndexName": "smart-tutor-index",
      "fieldMapping": {
        "vectorField": "embedding",
        "textField": "text",
        "metadataField": "metadata"
      }
    }
  }'
```

**Status:** ⏸️ Pending
**Dependencies:** OpenSearch Serverless collection

---

### 3. Code Implementation

#### 3.1 Bedrock LLM Adapter
**File:** `backend/bedrock_llm.py`

```python
"""AWS Bedrock LLM Adapter"""

import boto3
import json
from typing import Optional, Dict, Any
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

class BedrockLLM:
    """AWS Bedrock LLM wrapper for Claude 3.5 Sonnet"""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1"
    ):
        self.model_id = model_id
        self.region = region
        self.client = boto3.client('bedrock-runtime', region_name=region)
        logger.info(f"Bedrock LLM initialized: {model_id}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response using Bedrock Claude"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())

            # Track cost
            input_tokens = response_body.get('usage', {}).get('input_tokens', 0)
            output_tokens = response_body.get('usage', {}).get('output_tokens', 0)
            cost = self._calculate_cost(input_tokens, output_tokens)

            logger.info(
                f"Bedrock request: {input_tokens} input + {output_tokens} output tokens, "
                f"cost: ${cost:.4f}"
            )

            return response_body['content'][0]['text']

        except Exception as e:
            logger.error(f"Bedrock generation error: {e}")
            raise

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for Claude 3.5 Sonnet"""
        # Claude 3.5 Sonnet pricing (as of Dec 2025)
        INPUT_COST_PER_1K = 0.003  # $3 per 1M tokens
        OUTPUT_COST_PER_1K = 0.015  # $15 per 1M tokens

        input_cost = (input_tokens / 1000) * INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * OUTPUT_COST_PER_1K

        return input_cost + output_cost
```

**Status:** ⏸️ Pending
**Dependencies:** boto3, AWS credentials

#### 3.2 Bedrock Embeddings Adapter
**File:** `backend/bedrock_embeddings.py`

```python
"""AWS Bedrock Embeddings Adapter"""

import boto3
import json
from typing import List
from backend.logger import get_logger

logger = get_logger(__name__)

class BedrockEmbeddings:
    """AWS Bedrock Titan Embeddings wrapper"""

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region: str = "us-east-1"
    ):
        self.model_id = model_id
        self.region = region
        self.client = boto3.client('bedrock-runtime', region_name=region)
        self.dimension = 1024  # Titan v2 dimension
        logger.info(f"Bedrock Embeddings initialized: {model_id}")

    def encode(self, texts: List[str], batch_size: int = 16, **kwargs) -> List[Optional[List[float]]]:
        """
        Generate embeddings for a list of texts using batch processing.

        Args:
            texts: A list of strings to embed.
            batch_size: The number of texts to process in a single batch.
            **kwargs: Additional arguments (unused).

        Returns:
            A list of embeddings. If an error occurs for a text, the corresponding
            item in the list will be None.
        """
        all_embeddings: List[Optional[List[float]]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                # Note: Bedrock Titan embeddings models do not support batching
                # in the same way as other models. We must iterate.
                # This implementation is kept for logical structure and future-proofing.
                batch_embeddings = []
                for text in batch:
                    request_body = {
                        "inputText": text[:8192],  # Titan v1 max input length
                        "dimensions": self.dimension,
                        "normalize": True
                    }
                    response = self.client.invoke_model(
                        modelId=self.model_id,
                        body=json.dumps(request_body)
                    )
                    response_body = json.loads(response['body'].read())
                    embedding = response_body.get('embedding')
                    if embedding:
                        batch_embeddings.append(embedding)
                    else:
                        # Log error and append None for this text
                        error_message = response_body.get('message', 'Unknown error')
                        logger.warning(
                            f"Bedrock embedding failed for a text in batch. "
                            f"Text (first 50 chars): '{text[:50]}...'. "
                            f"Error: {error_message}"
                        )
                        batch_embeddings.append(None)
                all_embeddings.extend(batch_embeddings)

            except self.client.exceptions.ValidationException as e:
                logger.error(f"Bedrock validation error (check input length/format): {e}")
                all_embeddings.extend([None] * len(batch))
            except self.client.exceptions.AccessDeniedException as e:
                logger.error(f"Bedrock access denied. Check IAM permissions: {e}")
                raise  # This is a fatal error
            except Exception as e:
                logger.error(f"Bedrock embedding error during batch processing: {e}", exc_info=True)
                all_embeddings.extend([None] * len(batch))

        return all_embeddings
```

**Status:** ⏸️ Pending

#### 3.3 LLM Provider Abstraction
**File:** `backend/llm_provider.py`

```python
"""LLM Provider Abstraction Layer"""

from enum import Enum
from typing import Optional
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

class LLMProvider(Enum):
    BEDROCK = "bedrock"
    OLLAMA = "ollama"

class LLMFactory:
    """Factory for creating LLM instances"""

    @staticmethod
    def create_llm(provider: Optional[str] = None):
        """Create LLM instance based on provider"""

        provider = provider or config.LLM_PROVIDER

        if provider == LLMProvider.BEDROCK.value:
            from backend.bedrock_llm import BedrockLLM
            logger.info("Using AWS Bedrock for LLM")
            return BedrockLLM(
                model_id=config.BEDROCK_MODEL_ID,
                region=config.AWS_REGION
            )

        elif provider == LLMProvider.OLLAMA.value:
            from llama_index.llms.ollama import Ollama
            logger.info("Using Ollama for LLM (local)")
            return Ollama(
                model=config.LLM_MODEL,
                base_url=config.OLLAMA_BASE_URL,
                request_timeout=config.LLM_REQUEST_TIMEOUT
            )

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def create_embeddings(provider: Optional[str] = None):
        """Create embeddings instance based on provider"""

        provider = provider or config.EMBEDDING_PROVIDER

        if provider == LLMProvider.BEDROCK.value:
            from backend.bedrock_embeddings import BedrockEmbeddings
            logger.info("Using AWS Bedrock for embeddings")
            return BedrockEmbeddings(
                model_id=config.BEDROCK_EMBEDDING_MODEL_ID,
                region=config.AWS_REGION
            )

        elif provider == LLMProvider.OLLAMA.value:
            from sentence_transformers import SentenceTransformer
            logger.info("Using HuggingFace for embeddings (local)")
            return SentenceTransformer(config.EMBEDDING_MODEL)

        else:
            raise ValueError(f"Unknown embedding provider: {provider}")
```

**Status:** ⏸️ Pending

---

### 4. Configuration Updates

#### 4.1 Environment Variables
**File:** `.env` (for local development only)

**IMPORTANT:** This file should be added to `.gitignore` and **NEVER** committed to version control.

```bash
# AWS Configuration (for local development with temporary credentials)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<your-temporary-access-key>
AWS_SECRET_ACCESS_KEY=<your-temporary-secret-key>
AWS_SESSION_TOKEN=<your-temporary-session-token> # If using STS

# LLM Provider (bedrock or ollama)
LLM_PROVIDER=ollama  # Change to 'bedrock' when ready
EMBEDDING_PROVIDER=ollama  # Change to 'bedrock' when ready

# AWS Bedrock Models
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# S3 Buckets
S3_DOCUMENTS_BUCKET=smart-ai-tutor-docs
S3_UPLOADS_BUCKET=smart-ai-tutor-uploads

# Bedrock Knowledge Base
BEDROCK_KB_ID=your-kb-id-here
BEDROCK_KB_ENABLED=false  # Enable when ready

# Cost Tracking
ENABLE_COST_TRACKING=true
COST_LOG_FILE=logs/bedrock_costs.jsonl
```

**Credential Management Strategy:**

- **Local Development:**
  - Use short-lived credentials from AWS SSO or `aws sts get-session-token`.
  - Store these temporary credentials in the `.env` file.

- **CI/CD Pipelines:**
  - Use OpenID Connect (OIDC) to securely provide temporary credentials to your pipeline.
  - Do not store long-lived credentials as CI/CD variables.

- **Production (ECS, Lambda, EC2):**
  - **DO NOT** use access keys.
  - Attach an IAM Role to your compute resource (e.g., ECS Task Role, EC2 Instance Profile).
  - The application will automatically use the credentials provided by the IAM role.

#### 4.2 Config.py Updates
**File:** `backend/config.py` (add these)

```python
# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # bedrock or ollama
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")

# AWS Bedrock
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
BEDROCK_EMBEDDING_MODEL_ID = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")

# S3 Buckets
S3_DOCUMENTS_BUCKET = os.getenv("S3_DOCUMENTS_BUCKET", "smart-ai-tutor-docs")
S3_UPLOADS_BUCKET = os.getenv("S3_UPLOADS_BUCKET", "smart-ai-tutor-uploads")

# Bedrock Knowledge Base
BEDROCK_KB_ID = os.getenv("BEDROCK_KB_ID", "")
BEDROCK_KB_ENABLED = os.getenv("BEDROCK_KB_ENABLED", "false").lower() == "true"

# Cost Tracking
ENABLE_COST_TRACKING = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
COST_LOG_FILE = os.getenv("COST_LOG_FILE", "logs/bedrock_costs.jsonl")
```

**Status:** ⏸️ Pending

---

### 5. Migration Strategy

#### 5.1 Phase 4A: Bedrock LLM Only (Week 1)
1. Implement BedrockLLM adapter
2. Update Tutor_chat.py to use LLMFactory
3. Test with Bedrock for generation, keep local embeddings
4. Verify response quality matches Ollama

#### 5.2 Phase 4B: Bedrock Embeddings (Week 2)
1. Implement BedrockEmbeddings adapter
2. Re-index documents with Titan embeddings
3. Test retrieval accuracy
4. Compare with HuggingFace embeddings

#### 5.3 Phase 4C: Knowledge Base Integration (Week 3)
1. Upload documents to S3
2. Create Bedrock Knowledge Base
3. Integrate KB into RAG pipeline
4. Performance testing and optimization

#### 5.4 Phase 4D: Cost Optimization (Week 4)
1. Implement cost tracking
2. Add caching for repeated queries
3. Optimize chunk sizes and retrieval
4. Set up cost alerts

---

### 6. Testing Plan

#### 6.1 Unit Tests
```python
# Test Bedrock LLM
def test_bedrock_llm_generate():
    llm = BedrockLLM()
    response = llm.generate("What is Python?")
    assert len(response) > 0
    assert isinstance(response, str)

# Test Bedrock Embeddings
def test_bedrock_embeddings():
    embeddings = BedrockEmbeddings()
    vectors = embeddings.encode(["test text"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 1024  # Titan v2 dimension
```

#### 6.2 Integration Tests
```python
# Test RAG pipeline with Bedrock
def test_rag_with_bedrock():
    engine = RAGQueryEngine(llm_provider="bedrock")
    response = engine.query("Explain Python decorators")
    assert response is not None
    assert len(response) > 100
```

#### 6.3 Performance Tests
- Response time < 3s (95th percentile)
- Embedding generation < 500ms
- Vector search < 200ms
- Cost per query < $0.01

---

### 7. Rollback Plan

If issues arise:

```bash
# Option 1: Switch back to Ollama via config
export LLM_PROVIDER=ollama
export EMBEDDING_PROVIDER=ollama
./manage_services.sh restart backend

# Option 2: Git rollback
git checkout main
./manage_services.sh restart backend

# Option 3: Feature flag
export BEDROCK_KB_ENABLED=false
```

---

## 📊 Cost Estimates

### AWS Bedrock Pricing (December 2025)

**Claude 3.5 Sonnet:**
- Input: $3.00 per 1M tokens
- Output: $15.00 per 1M tokens

**Titan Embeddings v2:**
- $0.00002 per 1,000 input tokens

**Estimated Monthly Cost (1,000 queries/day):**
- LLM (avg 500 input + 1000 output tokens): ~$540/month
- Embeddings (avg 10 chunks × 200 tokens): ~$1.20/month
- S3 storage (100GB): ~$2.30/month
- **Total:** ~$545/month

**Cost Optimization:**
- Cache common queries (50% reduction)
- Use smaller model for simple queries
- Implement token limits
- **Optimized:** ~$270/month

---

## 🚀 Next Actions

1. **Immediate (This Week):**
   - [ ] Request AWS Bedrock access
   - [ ] Create boto3 requirements
   - [ ] Implement BedrockLLM adapter
   - [ ] Add LLM provider abstraction

2. **Short-term (Next 2 Weeks):**
   - [ ] Set up S3 buckets
   - [ ] Implement BedrockEmbeddings
   - [ ] Test Bedrock integration
   - [ ] Cost tracking implementation

3. **Medium-term (Next Month):**
   - [ ] Knowledge Base setup
   - [ ] Full migration to Bedrock
   - [ ] Performance optimization
   - [ ] Cost optimization

---

**Phase 4 Status:** 🚀 **READY TO START**
**Dependencies:** AWS account setup, Bedrock access request
**Estimated Duration:** 4 weeks
**Risk Level:** Medium (new AWS service, cost considerations)

---

*Last Updated: 2025-12-16*
