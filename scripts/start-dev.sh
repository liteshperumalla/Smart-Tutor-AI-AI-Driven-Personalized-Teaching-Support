#!/bin/bash

# Development Startup Script for Smart AI Tutor
# This script starts all services required for local development

set -e  # Exit on error

echo "========================================="
echo "Smart AI Tutor - Development Startup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "→ $1"
}

# Check if Docker is running
print_info "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi
print_success "Docker is running"

# Check if docker-compose is available
print_info "Checking docker-compose..."
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose not found. Please install Docker Compose."
    exit 1
fi
print_success "docker-compose is available"

# Check for .env file
print_info "Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env file not found"
    if [ -f ".env.example" ]; then
        print_info "Copying .env.example to .env..."
        cp .env.example .env
        print_success "Created .env file from .env.example"
        print_warning "Please review and update .env with your configuration"
    else
        print_error ".env.example not found. Cannot create .env file."
        exit 1
    fi
else
    print_success "Environment file exists"
fi

# Check for frontend .env.local
print_info "Checking frontend environment..."
if [ ! -f "frontend/.env.local" ]; then
    print_warning "frontend/.env.local not found"
    if [ -f "frontend/.env.local.example" ]; then
        print_info "Copying frontend/.env.local.example to frontend/.env.local..."
        cp frontend/.env.local.example frontend/.env.local
        print_success "Created frontend/.env.local file"
    else
        print_warning "frontend/.env.local.example not found"
    fi
else
    print_success "Frontend environment file exists"
fi

# Create required directories
print_info "Creating required directories..."
mkdir -p logs user_data previous_chats quiz_results persisted_index chroma_db keys
print_success "Directories created"

# Stop any existing containers
print_info "Stopping existing containers..."
docker-compose down > /dev/null 2>&1 || true
print_success "Existing containers stopped"

# Start infrastructure services first
print_info "Starting infrastructure services (PostgreSQL, DynamoDB, Redis)..."
docker-compose up -d postgres dynamodb-local redis

# Wait for databases to be healthy
print_info "Waiting for databases to be ready..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U smart_tutor_user -d smart_tutor > /dev/null 2>&1; then
        print_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "PostgreSQL failed to start within 30 seconds"
        docker-compose logs postgres
        exit 1
    fi
    sleep 1
done

for i in {1..30}; do
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        print_success "Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Redis failed to start within 30 seconds"
        docker-compose logs redis
        exit 1
    fi
    sleep 1
done

print_success "All infrastructure services are ready"

# Start backend and frontend
print_info "Starting backend and frontend services..."
docker-compose up -d backend frontend

# Wait for backend to be healthy
print_info "Waiting for backend to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:8010/health > /dev/null 2>&1; then
        print_success "Backend is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        print_error "Backend failed to start within 60 seconds"
        print_info "Backend logs:"
        docker-compose logs --tail=50 backend
        exit 1
    fi
    sleep 1
done

# Wait for frontend to be ready
print_info "Waiting for frontend to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:4000 > /dev/null 2>&1; then
        print_success "Frontend is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        print_error "Frontend failed to start within 60 seconds"
        print_info "Frontend logs:"
        docker-compose logs --tail=50 frontend
        exit 1
    fi
    sleep 1
done

echo ""
echo "========================================="
echo -e "${GREEN}✓ All services started successfully!${NC}"
echo "========================================="
echo ""
echo "Services:"
echo "  Frontend:     http://localhost:4000"
echo "  Backend API:  http://localhost:8010"
echo "  API Docs:     http://localhost:8010/docs"
echo "  PostgreSQL:   localhost:5432"
echo "  DynamoDB:     localhost:8001"
echo "  Redis:        localhost:6380"
echo ""
echo "Commands:"
echo "  View logs:    docker-compose logs -f [service]"
echo "  Stop all:     docker-compose down"
echo "  Restart:      docker-compose restart [service]"
echo ""
echo "Press Ctrl+C to stop following logs..."
echo ""

# Follow logs
docker-compose logs -f
