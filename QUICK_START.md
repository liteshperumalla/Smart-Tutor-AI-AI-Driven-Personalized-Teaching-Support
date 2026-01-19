# Quick Start Guide - Smart AI Tutor

## ⚡ Fastest Way to Get Started

### Prerequisites
- Docker and Docker Compose installed
- 8GB RAM minimum
- 10GB free disk space

### One-Command Startup

```bash
# Make script executable (first time only)
chmod +x scripts/start-dev.sh

# Start everything
./scripts/start-dev.sh
```

That's it! The script will:
1. ✅ Check Docker is running
2. ✅ Create .env files if missing
3. ✅ Create required directories
4. ✅ Start PostgreSQL, DynamoDB, Redis
5. ✅ Start Backend API
6. ✅ Start Frontend
7. ✅ Wait for all health checks
8. ✅ Display service URLs

### Access Your Application

- **Frontend**: http://localhost:4000
- **Backend API**: http://localhost:8010
- **API Documentation**: http://localhost:8010/docs

### Default Test Account

```
Username: admin
Password: Admin@123
```

Or create a new account at: http://localhost:4000/signup

## 🛠️ Manual Setup (Alternative)

If you prefer manual control:

### Step 1: Environment Configuration

```bash
# Copy environment templates
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local

# Edit .env files with your settings (optional)
nano .env
nano frontend/.env.local
```

### Step 2: Start Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Step 3: Verify Services

```bash
# Check all services are running
docker-compose ps

# Test backend health
curl http://localhost:8010/health

# Test frontend
curl http://localhost:4000
```

## 🔧 Common Commands

### Service Management

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart backend

# View logs for a service
docker-compose logs -f backend

# View all logs
docker-compose logs -f
```

### Database Management

```bash
# Access PostgreSQL
docker-compose exec postgres psql -U smart_tutor_user -d smart_tutor

# Access Redis CLI
docker-compose exec redis redis-cli

# List DynamoDB tables
aws dynamodb list-tables --endpoint-url http://localhost:8001
```

### Troubleshooting

```bash
# Remove all containers and volumes (CAUTION: Deletes all data)
docker-compose down -v

# Rebuild and restart
docker-compose up --build

# Check service health
docker-compose ps
curl http://localhost:8010/health/detailed
```

## 📦 What Gets Started?

| Service | Port | Description |
|---------|------|-------------|
| **Frontend** | 4000 | Next.js React application |
| **Backend** | 8010 | FastAPI REST API |
| **PostgreSQL** | 5432 | User data & structured storage |
| **DynamoDB Local** | 8001 | Chat sessions & NoSQL data |
| **Redis** | 6380 | Caching layer |

## 🎯 First Steps After Startup

1. **Create an Account**: http://localhost:4000/signup
2. **Login**: http://localhost:4000/login
3. **Start Chatting**: http://localhost:4000/chat
4. **Try a Quiz**: http://localhost:4000/quiz
5. **Explore Research**: http://localhost:4000/research

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker info

# Check port conflicts
lsof -i :4000
lsof -i :8010

# Check logs for errors
docker-compose logs backend
docker-compose logs frontend
```

### Database Connection Issues

```bash
# Verify PostgreSQL is ready
docker-compose exec postgres pg_isready

# Check database exists
docker-compose exec postgres psql -U smart_tutor_user -l
```

### Frontend Can't Connect to Backend

```bash
# Check backend is healthy
curl http://localhost:8010/health

# Check network connectivity
docker-compose exec frontend curl http://backend:8000/health

# Verify environment variables
docker-compose exec frontend env | grep API
```

### Reset Everything

```bash
# Stop and remove all containers, volumes, networks
docker-compose down -v

# Start fresh
./scripts/start-dev.sh
```

## 🚀 Production Deployment

For production deployment, see:
- **DEPLOYMENT_GUIDE.md** - Complete production guide
- **docker-compose.yml** - Can be adapted for production

Key production changes:
- Use AWS RDS instead of local PostgreSQL
- Use AWS DynamoDB instead of DynamoDB Local
- Use AWS ElastiCache instead of local Redis
- Enable HTTPS with SSL certificates
- Use AWS Secrets Manager for sensitive data
- Set `ENVIRONMENT=production` in .env

## 📚 Next Steps

- **Learn More**: Read IMPROVEMENTS_README.md
- **Detailed Analysis**: See COMPREHENSIVE_FIXES_SUMMARY.md
- **Deploy**: Follow DEPLOYMENT_GUIDE.md
- **API Reference**: http://localhost:8010/docs

## 💡 Tips

1. **Use Docker Desktop** for easier management and monitoring
2. **Keep logs open** during development to catch errors early
3. **Check health endpoint** if services seem unresponsive
4. **Restart services** if you change environment variables
5. **Review .env files** before first run

## 📞 Need Help?

1. Check **COMPREHENSIVE_FIXES_SUMMARY.md** for detailed information
2. Review **DEPLOYMENT_GUIDE.md** for troubleshooting
3. Check service logs: `docker-compose logs [service]`
4. Verify health: `curl http://localhost:8010/health/detailed`

---

**Happy Coding! 🎉**

Start here → `./scripts/start-dev.sh` → http://localhost:4000
