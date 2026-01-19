# Production Deployment Checklist

**Application:** Smart AI Tutor Backend
**Version:** 1.0.0
**Date:** December 28, 2024

---

## 🚨 CRITICAL - Complete Before Any Deployment

### 1. Rotate All Exposed Credentials

**Status:** ⏳ REQUIRED

All credentials in the original `.env` file were exposed and MUST be rotated:

```bash
# AWS Access Keys
aws iam delete-access-key --access-key-id AKIASVQKHKYNYFWLE4NK --user-name smart-tutor
aws iam create-access-key --user-name smart-tutor

# Database Password
# Change in RDS console or via AWS CLI

# Generate new JWT secret (RS256 recommended)
ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwt_private.pem
ssh-keygen -f keys/jwt_private.pem -e -m PEM > keys/jwt_public.pem

# Rotate Google OAuth secret in Google Cloud Console
# Rotate SMTP password in Gmail settings
# Rotate all API keys (Langfuse, SerpAPI, OpenAI)
```

**Verification:**
```bash
# Ensure old credentials don't work
aws sts get-caller-identity  # Should fail with old keys
```

---

### 2. Configure AWS Secrets Manager

**Status:** ⏳ REQUIRED

```bash
# Create main application secrets
aws secretsmanager create-secret \
  --name smart-tutor/app/secrets \
  --description "Smart AI Tutor application secrets" \
  --secret-string '{
    "jwt_secret_key": "<GENERATE-SECURE-KEY>",
    "serpapi_api_key": "<YOUR-NEW-KEY>",
    "langfuse_public_key": "<YOUR-NEW-KEY>",
    "langfuse_secret_key": "<YOUR-NEW-KEY>",
    "google_oauth_client_secret": "<YOUR-NEW-SECRET>",
    "smtp_password": "<YOUR-NEW-PASSWORD>",
    "smtp_username": "your-email@gmail.com"
  }'

# Create RDS credentials secret
aws secretsmanager create-secret \
  --name smart-tutor/rds/credentials \
  --description "Smart AI Tutor RDS database credentials" \
  --secret-string '{
    "host": "smart-tutor-postgres.cmfouoe8c2p1.us-east-1.rds.amazonaws.com",
    "port": "5432",
    "database": "smart_tutor",
    "username": "smart_tutor_admin",
    "password": "<NEW-SECURE-PASSWORD>"
  }'
```

**Verification:**
```bash
# Test secret retrieval
aws secretsmanager get-secret-value --secret-id smart-tutor/app/secrets
python -c "from backend.config import config; print('JWT Secret:', 'SET' if config.JWT_SECRET_KEY else 'NOT SET')"
```

---

### 3. Set Production Environment Variables

**Status:** ⏳ REQUIRED

Create production `.env` or set via ECS/EC2 environment:

```bash
# Core Configuration
ENVIRONMENT=production
DEBUG=false

# CORS - MUST SET ACTUAL DOMAINS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
CORS_ALLOW_LOCALHOST=false

# Security
ENFORCE_HTTPS=true
JWT_ALGORITHM=RS256

# AWS Configuration (use IAM roles in production)
AWS_REGION=us-east-1
# Do NOT set AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY - use IAM roles

# Database
STORAGE_BACKEND=hybrid
# Postgres credentials loaded from Secrets Manager

# Redis
USE_REDIS_CACHE=true
REDIS_HOST=<your-redis-endpoint>
REDIS_PORT=6379
REDIS_SSL=true

# LLM
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=meta.llama3-70b-instruct-v1:0
BEDROCK_REGION=us-east-1
```

**Verification:**
```bash
# Run configuration validation
python -c "from backend.config import config; result = config.validate(); print(result)"
```

---

### 4. Run Security Verification

**Status:** ⏳ REQUIRED

```bash
# Run the security verification script
python scripts/verify_security.py

# Expected output:
# ✅ SECURITY VERIFICATION PASSED
# All critical security checks passed!
```

**If verification fails:** Fix all errors before proceeding.

---

### 5. Configure IAM Roles (Production)

**Status:** ⏳ REQUIRED for EC2/ECS

Create IAM role with permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:smart-tutor/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::smart-tutor-vectors",
        "arn:aws:s3:::smart-tutor-vectors/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/smart-tutor-*"
      ]
    }
  ]
}
```

**Attach to:** EC2 instance or ECS task role

---

## ✅ Pre-Flight Checks

### Application Health

- [ ] **Health endpoint works**
  ```bash
  curl http://localhost:8000/health
  # Expected: {"status": "healthy"}
  ```

- [ ] **Detailed health check passes**
  ```bash
  curl http://localhost:8000/health/detailed
  # All components should be "healthy"
  ```

- [ ] **Database connection works**
  ```bash
  python -c "from backend.database import get_user_db; db = get_user_db(); print('DB OK')"
  ```

- [ ] **Redis connection works**
  ```bash
  python -c "from backend.redis_cache import RedisCache; r = RedisCache(); r.client.ping(); print('Redis OK')"
  ```

- [ ] **Bedrock access works**
  ```bash
  python -c "import boto3; sts = boto3.client('sts'); print(sts.get_caller_identity())"
  ```

### Security Checks

- [ ] **No secrets in .env file**
  ```bash
  grep -E "(AWS_ACCESS_KEY|AWS_SECRET|password=|api_key=)" .env
  # Should return nothing or only empty/commented lines
  ```

- [ ] **JWT tokens include JTI**
  ```bash
  python -c "from backend.jwt_service import get_jwt_service; import jwt; token = get_jwt_service().create_access_token('test', 'test@test.com'); payload = jwt.decode(token, options={'verify_signature': False}); print('JTI present:', 'jti' in payload)"
  ```

- [ ] **JWT blacklist initialized**
  ```bash
  python -c "from backend.jwt_blacklist import get_jwt_blacklist; print('Blacklist initialized:', get_jwt_blacklist() is not None)"
  ```

- [ ] **File validator works**
  ```bash
  python -c "from backend.file_validator import FileValidator; print('Validator OK')"
  ```

### Configuration Validation

- [ ] **Production config passes validation**
  ```bash
  ENVIRONMENT=production python -c "from backend.config import config; result = config.validate(); assert result['valid'], result['errors']; print('Config OK')"
  ```

- [ ] **CORS configured for production**
  ```bash
  python -c "import os; origins = os.getenv('CORS_ALLOWED_ORIGINS', ''); assert origins and 'yourdomain' not in origins, 'Set real domains!'; print('CORS OK')"
  ```

- [ ] **HTTPS enforcement enabled**
  ```bash
  python -c "from backend.config import config; assert config.ENFORCE_HTTPS if config.ENVIRONMENT == 'production' else True; print('HTTPS OK')"
  ```

---

## 🚀 Deployment Steps

### Option A: Docker Deployment

```bash
# 1. Build Docker image
docker build -t smart-ai-tutor-backend:1.0.0 -f Dockerfile .

# 2. Tag for registry
docker tag smart-ai-tutor-backend:1.0.0 <your-registry>/smart-ai-tutor-backend:1.0.0

# 3. Push to registry
docker push <your-registry>/smart-ai-tutor-backend:1.0.0

# 4. Deploy (ECS/EC2/K8s)
# Use your deployment tool to deploy the image
```

### Option B: Direct Deployment

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements-security.txt

# 2. Run migrations (if using Postgres)
# alembic upgrade head

# 3. Start application
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 📊 Post-Deployment Verification

### Smoke Tests

```bash
# 1. Health check
curl https://api.yourdomain.com/health
# Expected: {"status": "healthy"}

# 2. Create user (test signup)
curl -X POST https://api.yourdomain.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"Test123!","email":"test@test.com"}'

# 3. Login
curl -X POST https://api.yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"Test123!"}'
# Expected: {"token": "...", "user": {...}}

# 4. Test authenticated endpoint
curl -H "Authorization: Bearer <token>" https://api.yourdomain.com/health/detailed

# 5. Test logout (token revocation)
curl -X POST https://api.yourdomain.com/auth/logout \
  -H "Authorization: Bearer <token>"

# 6. Verify token is blacklisted
curl -H "Authorization: Bearer <token>" https://api.yourdomain.com/health/detailed
# Expected: 401 Unauthorized
```

### Monitor Logs

```bash
# Check for errors
tail -f logs/backend.log

# Monitor for security issues
grep -i "error\|critical\|security" logs/backend.log
```

### Check Metrics

- [ ] Monitor CPU/Memory usage
- [ ] Monitor Redis connection pool
- [ ] Monitor Database connection pool
- [ ] Monitor Bedrock API calls and costs
- [ ] Check error rates in logs

---

## 🔄 Rollback Plan

If issues are detected:

```bash
# 1. Stop new deployment
docker stop <container> || systemctl stop smart-tutor

# 2. Restore previous version
docker run <previous-version>

# 3. Check database state
# If migrations were run, may need to rollback:
# alembic downgrade -1

# 4. Verify health
curl http://localhost:8000/health

# 5. Investigate issues in logs
tail -n 1000 logs/backend.log
```

---

## 📞 Support Contacts

- **DevOps Team:** devops@yourcompany.com
- **Security Team:** security@yourcompany.com
- **On-Call Engineer:** See PagerDuty

---

## 📝 Post-Deployment Tasks

- [ ] Delete `.env.backup` file (contains old secrets)
- [ ] Update DNS records if needed
- [ ] Configure CloudWatch alarms
- [ ] Setup automated backups
- [ ] Enable CloudWatch logging
- [ ] Configure auto-scaling (if applicable)
- [ ] Run security scan (bandit, safety)
- [ ] Update documentation with production URLs
- [ ] Notify team of successful deployment

---

## ✅ Deployment Sign-Off

**Deployed By:** _________________

**Date:** _________________

**Version:** 1.0.0

**Environment:** Production

**Approval:**
- [ ] Security Team: _________________
- [ ] DevOps Team: _________________
- [ ] Product Owner: _________________

---

**Notes:**

_Add any deployment-specific notes here_

---

## 🎉 Success Criteria

Deployment is successful when:
- ✅ All health checks pass
- ✅ Smoke tests complete successfully
- ✅ No errors in logs for 15 minutes
- ✅ Authentication flow works (signup, login, logout)
- ✅ JWT blacklist working (logged out tokens rejected)
- ✅ All AWS services accessible (Secrets Manager, Bedrock, DynamoDB, RDS)
- ✅ File uploads working with validation
- ✅ Rate limiting functioning properly
- ✅ CORS configured correctly (no 403 errors from frontend)

**Congratulations! Smart AI Tutor is now securely deployed! 🚀**
