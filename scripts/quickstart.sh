#!/bin/bash
#
# Quick Start Script for Smart AI Tutor
# Sets up development environment quickly
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "=================================================="
echo "  Smart AI Tutor - Quick Start"
echo "=================================================="
echo -e "${NC}"

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Check if we're in the project root
if [ ! -f "backend/config.py" ]; then
    echo -e "${RED}Error: Must run from project root${NC}"
    exit 1
fi

# Step 1: Create virtual environment
echo -e "\n${BLUE}Step 1: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}! Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Step 2: Install dependencies
echo -e "\n${BLUE}Step 2: Installing dependencies...${NC}"
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Step 3: Install security dependencies (optional)
echo -e "\n${BLUE}Step 3: Installing security tools...${NC}"
pip install -r backend/requirements-security.txt 2>&1 | grep -v "already satisfied" || true
echo -e "${GREEN}✓ Security tools installed${NC}"

# Step 4: Setup environment file
echo -e "\n${BLUE}Step 4: Setting up environment file...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env from .env.example${NC}"
        echo -e "${YELLOW}! Please edit .env with your configuration${NC}"
    else
        echo -e "${YELLOW}! .env.example not found, skipping${NC}"
    fi
else
    echo -e "${YELLOW}! .env already exists${NC}"
fi

# Step 5: Create required directories
echo -e "\n${BLUE}Step 5: Creating required directories...${NC}"
mkdir -p logs uploads user_data keys
echo -e "${GREEN}✓ Directories created${NC}"

# Step 6: Generate JWT keys (development only)
echo -e "\n${BLUE}Step 6: Generating JWT keys for development...${NC}"
if [ ! -f "keys/jwt_private.pem" ]; then
    ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwt_private.pem -N "" -q
    ssh-keygen -f keys/jwt_private.pem -e -m PEM > keys/jwt_public.pem
    chmod 600 keys/jwt_private.pem
    chmod 644 keys/jwt_public.pem
    echo -e "${GREEN}✓ JWT RSA keys generated${NC}"
else
    echo -e "${YELLOW}! JWT keys already exist${NC}"
fi

# Step 7: Setup database (if using Docker)
echo -e "\n${BLUE}Step 7: Database setup...${NC}"
echo "Do you want to start Docker services (PostgreSQL, Redis)? (y/N)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d postgres redis
        echo -e "${GREEN}✓ Docker services started${NC}"
        echo "Waiting for services to be ready..."
        sleep 5
    else
        echo -e "${RED}✗ docker-compose not found${NC}"
    fi
else
    echo -e "${YELLOW}! Skipping Docker services${NC}"
fi

# Step 8: Run security setup
echo -e "\n${BLUE}Step 8: Running security setup...${NC}"
if [ -f "scripts/setup-security.sh" ]; then
    bash scripts/setup-security.sh
else
    echo -e "${YELLOW}! Security setup script not found${NC}"
fi

# Step 9: Verify installation
echo -e "\n${BLUE}Step 9: Verifying installation...${NC}"
python -c "from backend.config import config; print('✓ Config loaded successfully')"
python -c "from backend.jwt_service import get_jwt_service; print('✓ JWT service OK')"
python -c "from backend.health import HealthChecker; print('✓ Health checker OK')"
echo -e "${GREEN}✓ All imports successful${NC}"

# Step 10: Display next steps
echo -e "\n${GREEN}=================================================="
echo "  Setup Complete! 🎉"
echo "==================================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Edit .env with your configuration:"
echo "   - Set JWT_SECRET_KEY (or use generated RSA keys)"
echo "   - Configure database connection"
echo "   - Set AWS credentials (or use IAM roles)"
echo ""
echo "2. Start the backend server:"
echo -e "   ${BLUE}uvicorn backend.api.main:app --reload${NC}"
echo ""
echo "3. Test the API:"
echo -e "   ${BLUE}curl http://localhost:8000/health${NC}"
echo ""
echo "4. View API documentation:"
echo "   http://localhost:8000/docs (development only)"
echo ""
echo "5. Run security verification:"
echo -e "   ${BLUE}python scripts/verify_security.py${NC}"
echo ""
echo -e "${YELLOW}For production deployment:${NC}"
echo "   See DEPLOYMENT_CHECKLIST.md"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
echo ""
