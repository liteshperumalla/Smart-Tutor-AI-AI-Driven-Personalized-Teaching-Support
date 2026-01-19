# Command Reference Card

Quick reference for all common commands.

---

## 🚀 Quick Start

```bash
# One-command setup (recommended)
./scripts/start-dev.sh

# Manual start
docker-compose up -d

# Stop all services
docker-compose down
```

---

## 🧪 Testing

### Backend Tests
```bash
cd backend

# Run all tests
pytest

# Verbose output
pytest -v

# With coverage
pytest --cov

# Specific test file
pytest tests/test_auth.py

# Specific test
pytest tests/test_auth.py::TestUserLogin::test_successful_login

# Only auth tests
pytest -m auth

# Generate HTML coverage report
pytest --cov --cov-report=html
open htmlcov/index.html  # View report
```

### Frontend Tests
```bash
cd frontend

# Run all tests
npm test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage

# Update snapshots
npm test -- -u

# Specific test file
npm test -- src/lib/__tests__/api-client.test.ts
```

### E2E Tests
```bash
cd e2e

# Run all E2E tests
npm run test:e2e

# Interactive mode
npm run test:e2e:ui

# Headed mode (see browser)
npm run test:e2e:headed

# Specific browser
npm run test:e2e -- --project=chromium

# Debug mode
npm run test:e2e -- --debug

# Generate report
npm run test:e2e -- --reporter=html
npx playwright show-report
```

---

## 🐳 Docker

### Service Management
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d backend

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Restart service
docker-compose restart backend

# Rebuild and start
docker-compose up --build

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend

# Tail logs (last 100 lines)
docker-compose logs --tail=100 backend

# Check service status
docker-compose ps

# Execute command in container
docker-compose exec backend python manage.py

# Access bash in container
docker-compose exec backend bash
```

### Docker Images
```bash
# Build images
docker build -t smart-tutor-backend -f backend/Dockerfile .
docker build -t smart-tutor-frontend -f frontend/Dockerfile ./frontend

# List images
docker images

# Remove image
docker rmi smart-tutor-backend

# Remove all unused images
docker image prune -a
```

---

## 🗄️ Database

### Alembic Migrations
```bash
cd backend

# Create new migration
alembic revision --autogenerate -m "description"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Show current version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic show <revision_id>
```

### PostgreSQL
```bash
# Access PostgreSQL
docker-compose exec postgres psql -U smart_tutor_user -d smart_tutor

# Backup database
docker-compose exec postgres pg_dump -U smart_tutor_user smart_tutor > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T postgres psql -U smart_tutor_user smart_tutor

# Check database size
docker-compose exec postgres psql -U smart_tutor_user -d smart_tutor \
  -c "SELECT pg_size_pretty(pg_database_size('smart_tutor'));"
```

### Redis
```bash
# Access Redis CLI
docker-compose exec redis redis-cli

# Check Redis info
docker-compose exec redis redis-cli INFO

# Clear all Redis data
docker-compose exec redis redis-cli FLUSHALL

# Monitor Redis commands
docker-compose exec redis redis-cli MONITOR
```

### DynamoDB
```bash
# List tables
aws dynamodb list-tables --endpoint-url http://localhost:8001

# Describe table
aws dynamodb describe-table \
  --table-name chat_sessions \
  --endpoint-url http://localhost:8001

# Scan table
aws dynamodb scan \
  --table-name chat_sessions \
  --endpoint-url http://localhost:8001
```

---

## 🔍 Monitoring

### Health Checks
```bash
# Basic health
curl http://localhost:8010/health

# Detailed health (all components)
curl http://localhost:8010/health/detailed | jq

# WebSocket status
curl http://localhost:8010/ws/status | jq
```

### Metrics
```bash
# Prometheus metrics
curl http://localhost:8010/metrics

# Specific metric
curl http://localhost:8010/metrics | grep http_requests_total

# Application metrics
curl http://localhost:8010/health/detailed | jq '.components'
```

### Logs
```bash
# View all logs
docker-compose logs -f

# Backend logs only
docker-compose logs -f backend

# Frontend logs only
docker-compose logs -f frontend

# Last 100 lines
docker-compose logs --tail=100

# Since specific time
docker-compose logs --since 30m

# Search logs
docker-compose logs backend | grep ERROR
```

---

## 🔐 Security

### JWT Tokens
```bash
# Get token (login)
curl -X POST http://localhost:8010/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"TestPass123!"}'

# Use token
export TOKEN="your-jwt-token-here"
curl http://localhost:8010/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Refresh token
curl -X POST http://localhost:8010/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"your-refresh-token"}'

# Logout
curl -X POST http://localhost:8010/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

### Security Scans
```bash
# Run Bandit (Python security)
bandit -r backend/

# Run Trivy (Docker security)
trivy image smart-tutor-backend:latest

# Check dependencies
pip-audit  # Python
npm audit  # Node.js
```

---

## 🚢 Deployment

### Local Deployment
```bash
# Start everything
./scripts/start-dev.sh

# Or manually
docker-compose up --build -d
```

### Git Workflow
```bash
# Deploy to staging
git checkout develop
git pull origin develop
git push origin develop  # Triggers CI/CD

# Deploy to production
git checkout main
git merge develop
git push origin main  # Triggers CI/CD with approval
```

### Manual Docker Push
```bash
# Login to Docker Hub
docker login

# Tag images
docker tag smart-tutor-backend:latest username/smart-tutor-backend:latest
docker tag smart-tutor-frontend:latest username/smart-tutor-frontend:latest

# Push images
docker push username/smart-tutor-backend:latest
docker push username/smart-tutor-frontend:latest
```

---

## 🛠️ Development

### Backend
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8010

# Format code
black .

# Lint code
flake8 .

# Type check
mypy .
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Format code
npm run format

# Lint code
npm run lint

# Type check
npm run type-check
```

---

## 📊 Utilities

### Database Utilities
```bash
# Standardize field names
python backend/scripts/standardize_fields.py

# Initialize database
python backend/scripts/init_db.py

# Seed test data
python backend/scripts/seed_data.py
```

### Performance
```bash
# Profile API endpoint
ab -n 1000 -c 10 http://localhost:8010/health

# Load test
locust -f tests/locustfile.py --host=http://localhost:8010
```

### Code Quality
```bash
# Check coverage
pytest --cov --cov-report=term-missing

# Generate coverage badge
coverage-badge -o coverage.svg

# Check code complexity
radon cc backend/ -a

# Find security issues
bandit -r backend/
```

---

## 🔄 CI/CD

### GitHub Actions
```bash
# View workflow runs
gh run list

# View specific run
gh run view <run-id>

# View logs
gh run view <run-id> --log

# Rerun failed jobs
gh run rerun <run-id>

# Watch run
gh run watch
```

---

## 🐛 Debugging

### Common Issues

**Services won't start**:
```bash
# Check Docker
docker info

# Check ports
lsof -i :4000
lsof -i :8010

# Restart Docker
docker-compose down
docker-compose up --build
```

**Tests failing**:
```bash
# Clear pytest cache
pytest --cache-clear

# Clear npm cache
npm test -- --clearCache

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
npm ci
```

**Database connection errors**:
```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready

# Check connection
docker-compose exec postgres psql -U smart_tutor_user -d smart_tutor -c "SELECT 1;"

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

**Frontend won't build**:
```bash
# Clear Next.js cache
rm -rf frontend/.next

# Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install

# Check for TypeScript errors
npm run type-check
```

---

## 📝 Quick Tips

### Productivity
```bash
# Create alias for common commands
alias dc='docker-compose'
alias dce='docker-compose exec'
alias dcl='docker-compose logs -f'

# Use them
dc up -d
dce backend pytest
dcl backend
```

### Shortcuts
```bash
# Rebuild and restart specific service
docker-compose up -d --build backend

# View only errors in logs
docker-compose logs backend | grep ERROR

# Get container IP
docker inspect smart-tutor-backend | grep IPAddress
```

---

## 🆘 Emergency Commands

### Quick Reset
```bash
# Nuclear option - reset everything
docker-compose down -v
rm -rf backend/__pycache__ frontend/.next
docker system prune -a
./scripts/start-dev.sh
```

### Rollback
```bash
# Git rollback
git revert HEAD
git push

# Docker rollback
docker-compose down
git checkout <previous-commit>
docker-compose up --build

# Database rollback
alembic downgrade -1
```

---

## 📞 Help

- **API Docs**: http://localhost:8010/docs
- **Health Check**: http://localhost:8010/health/detailed
- **Logs**: `docker-compose logs -f [service]`
- **Documentation**: See INDEX_ALL_IMPLEMENTATIONS.md

---

**Last Updated**: 2025-12-28
**Version**: 1.0
