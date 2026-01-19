# Smart AI Tutor - Production Deployment Guide

**Last Updated**: 2025-12-19
**Status**: Ready for Production Deployment

---

## 🚀 Quick Start

To deploy the complete production stack:

```bash
./deploy_production.sh
```

This interactive script will guide you through all deployment steps.

---

## 📋 Production Readiness Checklist

### Prerequisites ✅

Before deploying, ensure you have:

- [x] AWS CLI configured with production credentials
- [x] AWS Account with Bedrock access enabled
- [x] RDS PostgreSQL instance created
- [x] DynamoDB tables created
- [x] S3 buckets created
- [x] Secrets Manager secrets configured
- [x] Docker and Docker Compose installed (for container deployment)
- [x] Domain name registered (for SSL/HTTPS)

### Security Configuration 🔐

Run these scripts to harden security:

1. **Rotate JWT Secret**
   ```bash
   ./rotate_jwt_secret.sh
   ```
   - Generates cryptographically secure JWT secret
   - Updates AWS Secrets Manager
   - Requires service restart

2. **Enable Secret Rotation**
   ```bash
   ./enable_secret_rotation.sh
   ```
   - Configures automatic rotation for RDS credentials
   - Documents JWT rotation process
   - Sets rotation intervals

### Backup & Recovery 💾

Ensure data protection:

3. **Verify RDS Backups**
   ```bash
   ./verify_rds_backups.sh
   ```
   - Checks automated backup configuration
   - Verifies retention period (recommended: 30 days)
   - Confirms encryption status

4. **Enable DynamoDB Point-in-Time Recovery**
   ```bash
   ./enable_dynamodb_pitr.sh
   ```
   - Enables continuous backups for all tables
   - 35-day restore window
   - No performance impact

### Monitoring & Alerts 📊

Setup comprehensive monitoring:

5. **CloudWatch Logs**
   ```bash
   ./setup_cloudwatch_logs.sh
   ```
   - Creates log groups for application, API, backend, errors
   - Configures retention policies
   - Sets up metric filters

6. **Error Alarms**
   ```bash
   ./setup_error_alarms.sh
   ```
   - Monitors API 5xx/4xx errors
   - Tracks Lambda failures
   - Detects Bedrock throttling
   - Sends SNS notifications

### Application Configuration 🌐

7. **Update CORS Settings**
   ```bash
   ./update_cors_production.sh
   ```
   - Configure production domain(s)
   - Disable localhost access
   - Enable HTTPS enforcement

8. **Environment Variables**

   Verify `.env` file contains:
   ```bash
   ENVIRONMENT=production
   DEBUG=false
   ENFORCE_HTTPS=true
   CORS_ALLOW_LOCALHOST=false
   CORS_ALLOWED_ORIGINS=https://yourdomain.com
   ```

---

## 🔧 Deployment Steps

### Option 1: Automated Deployment

```bash
# Run the complete deployment script
./deploy_production.sh
```

The script will:
1. Check prerequisites
2. Rotate secrets
3. Enable backups
4. Setup monitoring
5. Update CORS
6. Verify environment
7. Build and test
8. Deploy services
9. Run health checks

### Option 2: Manual Deployment

#### Step 1: Prepare Environment

```bash
# Copy and configure .env
cp .env.example .env
nano .env

# Verify configuration
source .env
echo "Environment: $ENVIRONMENT"
```

#### Step 2: Deploy Infrastructure

```bash
# Run AWS setup scripts
./setup_secrets_manager.sh
./setup_rds_postgres.sh
./setup_aws_dynamodb.sh
./setup_cloudwatch_alarms.sh
```

#### Step 3: Deploy Application

**Using Docker Compose:**
```bash
docker-compose down
docker-compose up -d --build

# View logs
docker-compose logs -f
```

**Manual deployment:**
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8010

# Frontend
cd frontend
npm install
npm run build
npm start
```

#### Step 4: Verify Deployment

```bash
# Check service health
curl http://localhost:8010/health
curl http://localhost:4000

# Check AWS connectivity
aws bedrock list-foundation-models --region us-east-1

# View logs
docker-compose logs backend
docker-compose logs frontend
```

---

## 🔒 SSL/TLS Setup

### Option 1: AWS Certificate Manager (ACM)

```bash
# Request certificate
aws acm request-certificate \
  --domain-name yourdomain.com \
  --subject-alternative-names "*.yourdomain.com" \
  --validation-method DNS \
  --region us-east-1

# Verify DNS validation records
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:... \
  --region us-east-1
```

### Option 2: Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

---

## 🌐 DNS Configuration

Point your domain to the application:

```
# Example DNS Records
Type    Name                Value                       TTL
A       @                   <your-server-ip>            300
A       www                 <your-server-ip>            300
CNAME   api                 <alb-dns-name>              300
```

For CloudFront:
```
CNAME   @                   <cloudfront-distribution>   300
```

---

## 📊 Monitoring & Observability

### CloudWatch Dashboards

Create custom dashboard:
```bash
aws cloudwatch put-dashboard \
  --dashboard-name SmartTutorProduction \
  --dashboard-body file://cloudwatch-dashboard.json
```

### Log Queries

View application errors:
```bash
aws logs tail /aws/smart-tutor/application \
  --follow \
  --filter-pattern "ERROR" \
  --region us-east-1
```

### Metrics

Key metrics to monitor:
- API latency (p50, p95, p99)
- Error rate (5xx, 4xx)
- Bedrock token usage
- RDS CPU/Connections
- DynamoDB throttling

---

## 🔄 CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy
        run: |
          ./deploy_production.sh
```

---

## 🧪 Testing Production

### Health Checks

```bash
# API health
curl https://api.yourdomain.com/health

# Database connectivity
curl https://api.yourdomain.com/health/db

# AWS services
curl https://api.yourdomain.com/health/aws
```

### Load Testing

```bash
# Install k6
brew install k6

# Run load test
k6 run loadtest.js
```

### Security Scanning

```bash
# Install OWASP ZAP
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://yourdomain.com
```

---

## 🚨 Incident Response

### Service Outage

1. Check CloudWatch alarms
2. Review recent deployments
3. Check AWS service health
4. Review application logs
5. Rollback if necessary

### Rollback Procedure

```bash
# Docker Compose
docker-compose down
git checkout <previous-commit>
docker-compose up -d

# Database rollback
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier smart-tutor-postgres \
  --target-db-instance-identifier smart-tutor-postgres-restored \
  --restore-time 2025-12-19T00:00:00Z
```

---

## 📝 Post-Deployment Checklist

After deployment, verify:

- [ ] All services are running
- [ ] SSL/TLS certificates are valid
- [ ] DNS records are propagated
- [ ] CloudWatch alarms are active
- [ ] Backups are configured and working
- [ ] Secrets are rotated
- [ ] CORS is properly configured
- [ ] Error notifications are working
- [ ] Performance is acceptable
- [ ] Security scanning passed
- [ ] Documentation is updated
- [ ] Team is trained on new deployment

---

## 📞 Support

For issues:
1. Check CloudWatch Logs
2. Review deployment logs
3. Consult AWS documentation
4. Contact DevOps team

---

## 🔗 Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)

---

**Deployment Status**: ✅ Ready for Production
**Last Tested**: 2025-12-19
**Maintained by**: Engineering Team
