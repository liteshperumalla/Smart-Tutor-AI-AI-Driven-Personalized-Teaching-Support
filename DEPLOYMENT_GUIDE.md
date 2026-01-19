# Smart AI Tutor - Deployment Guide

## Overview

This guide covers deploying the Smart AI Tutor application using Docker Compose for development and production environments.

## Prerequisites

- Docker 20.10+ and Docker Compose V2
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)
- AWS Account (for production with Bedrock, S3, DynamoDB, RDS)
- Domain name (for production HTTPS)

## Architecture

```
┌─────────────────┐      ┌─────────────────┐
│   Frontend      │────▶ │   Backend API   │
│   (Next.js)     │      │   (FastAPI)     │
│   Port: 4000    │      │   Port: 8000    │
└─────────────────┘      └─────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐   ┌────────▼────────┐   ┌────────▼────────┐
│  PostgreSQL    │   │   DynamoDB      │   │     Redis       │
│  (User Data)   │   │ (Chat Sessions) │   │   (Caching)     │
│  Port: 5432    │   │  Port: 8001     │   │  Port: 6380     │
└────────────────┘   └─────────────────┘   └─────────────────┘
```

## Quick Start (Development)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd Smart\ AI\ Tutor
```

### 2. Environment Configuration

Copy and configure environment files:

```bash
# Backend environment
cp .env.example .env

# Frontend environment
cp frontend/.env.local.example frontend/.env.local
```

**Required Environment Variables:**

Backend (`.env`):
```env
ENVIRONMENT=development
DEBUG=true
STORAGE_BACKEND=hybrid

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=smart_tutor
POSTGRES_USER=smart_tutor_user
POSTGRES_PASSWORD=dev_password_change_in_prod

# DynamoDB
DYNAMODB_ENDPOINT=http://dynamodb-local:8000
DYNAMODB_REGION=us-east-1

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
USE_REDIS_CACHE=true

# JWT
JWT_ALGORITHM=HS256
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:4000
CORS_ALLOW_LOCALHOST=true

# Optional: AWS Bedrock (for production)
LLM_PROVIDER=ollama  # or bedrock
AWS_REGION=us-east-1
```

Frontend (`frontend/.env.local`):
```env
NEXT_PUBLIC_API_BASE_URL=/api/backend
BACKEND_API_BASE_URL=http://localhost:8010
NEXT_PUBLIC_APP_BASE_URL=http://localhost:4000
NEXT_PUBLIC_BACKEND_PORT=8010

# Optional: Google OAuth
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=http://localhost:4000/auth/google/callback
```

### 3. Start Services

```bash
# Start all services (first time)
docker-compose up --build

# Start services (subsequent runs)
docker-compose up

# Run in background
docker-compose up -d
```

### 4. Access the Application

- **Frontend**: http://localhost:4000
- **Backend API**: http://localhost:8010
- **API Docs**: http://localhost:8010/docs

### 5. Stop Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

## Production Deployment

### 1. AWS Infrastructure Setup

#### RDS PostgreSQL
```bash
# Create RDS instance
aws rds create-db-instance \
    --db-instance-identifier smart-tutor-prod \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username admin \
    --master-user-password <secure-password> \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxx \
    --backup-retention-period 7 \
    --publicly-accessible false
```

#### DynamoDB Tables
```bash
# Create chat sessions table
aws dynamodb create-table \
    --table-name smart-tutor-chat-sessions \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=session_id,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
        AttributeName=session_id,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES
```

#### ElastiCache Redis
```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
    --cache-cluster-id smart-tutor-redis \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --num-cache-nodes 1 \
    --security-group-ids sg-xxxxx
```

#### AWS Secrets Manager
```bash
# Store application secrets
aws secretsmanager create-secret \
    --name smart-tutor/app/secrets \
    --secret-string '{
        "jwt_secret_key": "<secure-random-key>",
        "serpapi_api_key": "<your-key>",
        "langfuse_public_key": "<your-key>",
        "langfuse_secret_key": "<your-key>",
        "google_oauth_client_id": "<your-key>",
        "google_oauth_client_secret": "<your-key>"
    }'

# Store RDS credentials
aws secretsmanager create-secret \
    --name smart-tutor/rds/credentials \
    --secret-string '{
        "host": "<rds-endpoint>",
        "port": 5432,
        "database": "smart_tutor",
        "username": "admin",
        "password": "<secure-password>"
    }'
```

### 2. Production Environment Configuration

Create production environment file:

```env
# .env.production
ENVIRONMENT=production
DEBUG=false
ENFORCE_HTTPS=true

# Database (loaded from Secrets Manager)
STORAGE_BACKEND=hybrid
POSTGRES_HOST=<rds-endpoint>
POSTGRES_PORT=5432
POSTGRES_DB=smart_tutor

# DynamoDB (AWS managed)
DYNAMODB_ENDPOINT=
DYNAMODB_REGION=us-east-1
DYNAMODB_TABLE_CHAT_SESSIONS=smart-tutor-chat-sessions

# Redis (ElastiCache)
USE_REDIS_CACHE=true
REDIS_HOST=<elasticache-endpoint>
REDIS_PORT=6379
REDIS_SSL=true

# JWT (RS256 for production)
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=/app/keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/app/keys/jwt_public.pem

# CORS (your production domains)
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
CORS_ALLOW_LOCALHOST=false

# AWS Bedrock
LLM_PROVIDER=bedrock
EMBEDDING_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=meta.llama3-70b-instruct-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Monitoring
LANGFUSE_ENABLED=true
CLOUDWATCH_ENABLED=true
CLOUDWATCH_LOG_GROUP=/aws/smart-ai-tutor/backend
```

### 3. Generate RSA Keys for JWT (Production)

```bash
# Generate private key
openssl genrsa -out keys/jwt_private.pem 4096

# Generate public key
openssl rsa -in keys/jwt_private.pem -pubout -out keys/jwt_public.pem

# Set proper permissions
chmod 600 keys/jwt_private.pem
chmod 644 keys/jwt_public.pem
```

### 4. Build Production Images

```bash
# Build backend
docker build -t smart-tutor-backend:latest -f backend/Dockerfile .

# Build frontend
docker build -t smart-tutor-frontend:latest \
    --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com \
    --build-arg NEXT_PUBLIC_APP_BASE_URL=https://yourdomain.com \
    ./frontend
```

### 5. Deploy to AWS ECS/EC2

```bash
# Push images to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

docker tag smart-tutor-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/smart-tutor-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/smart-tutor-backend:latest

docker tag smart-tutor-frontend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/smart-tutor-frontend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/smart-tutor-frontend:latest
```

### 6. HTTPS Setup with Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot

# Obtain certificates
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# Certificates will be in /etc/letsencrypt/live/yourdomain.com/
```

## Monitoring and Logging

### Health Checks

- Backend: `GET /health`
- Detailed: `GET /health/detailed`

### CloudWatch Logs

```bash
# View logs
aws logs tail /aws/smart-ai-tutor/backend --follow

# View specific stream
aws logs get-log-events \
    --log-group-name /aws/smart-ai-tutor/backend \
    --log-stream-name <stream-name>
```

### Langfuse Monitoring

Access Langfuse dashboard at: https://cloud.langfuse.com

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker-compose logs backend

# Verify database connection
docker-compose exec backend python -c "from backend.database import get_user_db; print(get_user_db())"

# Check environment variables
docker-compose exec backend env | grep -E "POSTGRES|DYNAMODB|REDIS"
```

### Frontend can't connect to backend

```bash
# Check network
docker-compose exec frontend curl http://backend:8000/health

# Verify environment variables
docker-compose exec frontend env | grep API
```

### Database connection issues

```bash
# Test PostgreSQL connection
docker-compose exec postgres psql -U smart_tutor_user -d smart_tutor -c "SELECT version();"

# Check DynamoDB tables
aws dynamodb list-tables --endpoint-url http://localhost:8001
```

## Backup and Recovery

### Database Backups

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U smart_tutor_user smart_tutor > backup.sql

# Restore PostgreSQL
cat backup.sql | docker-compose exec -T postgres psql -U smart_tutor_user smart_tutor
```

### DynamoDB Backups

```bash
# Create backup
aws dynamodb create-backup \
    --table-name smart-tutor-chat-sessions \
    --backup-name smart-tutor-backup-$(date +%Y%m%d)
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Enable HTTPS in production
- [ ] Rotate JWT keys regularly
- [ ] Enable AWS Secrets Manager for sensitive data
- [ ] Configure proper CORS origins
- [ ] Enable rate limiting
- [ ] Set up CloudWatch alarms
- [ ] Enable RDS encryption at rest
- [ ] Enable DynamoDB point-in-time recovery
- [ ] Use IAM roles instead of access keys
- [ ] Enable MFA for AWS console access
- [ ] Regular security audits and dependency updates

## Performance Optimization

### Frontend
- Enable Next.js image optimization
- Use static generation where possible
- Implement code splitting
- Enable CDN for static assets

### Backend
- Enable Redis caching
- Use connection pooling
- Implement request rate limiting
- Optimize database queries with indexes
- Use AWS Bedrock for scalable LLM inference

### Database
- Create indexes on frequently queried fields
- Enable query performance insights
- Use read replicas for high traffic
- Implement database connection pooling

## Cost Optimization

- Use AWS Budgets and Cost Explorer
- Implement auto-scaling for ECS services
- Use Spot Instances where appropriate
- Enable DynamoDB on-demand billing
- Monitor Bedrock usage and costs
- Set up cost alerts

## Support

For issues and questions:
- Check logs: `docker-compose logs`
- Review API docs: http://localhost:8010/docs
- Contact: support@smartaitutor.com
