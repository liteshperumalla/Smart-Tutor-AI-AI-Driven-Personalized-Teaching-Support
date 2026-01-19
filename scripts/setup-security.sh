#!/bin/bash
#
# Security Setup Script
# Configures security features for Smart AI Tutor backend
#

set -e  # Exit on error

echo "=================================================="
echo "Smart AI Tutor - Security Setup"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in project root
if [ ! -f "backend/config.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

echo "Step 1: Installing security dependencies..."
pip install python-magic bandit safety pre-commit 2>&1 | grep -v "already satisfied" || true

echo ""
echo "Step 2: Setting up pre-commit hooks..."
pre-commit install

echo ""
echo "Step 3: Creating secrets baseline..."
if [ ! -f ".secrets.baseline" ]; then
    detect-secrets scan > .secrets.baseline 2>/dev/null || echo "{}" > .secrets.baseline
    echo -e "${GREEN}✓ Secrets baseline created${NC}"
else
    echo -e "${YELLOW}! Secrets baseline already exists${NC}"
fi

echo ""
echo "Step 4: Generating JWT RSA keys (if needed)..."
mkdir -p keys

if [ ! -f "keys/jwt_private.pem" ]; then
    ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwt_private.pem -N "" -q
    chmod 600 keys/jwt_private.pem
    echo -e "${GREEN}✓ JWT private key generated${NC}"
else
    echo -e "${YELLOW}! JWT private key already exists${NC}"
fi

if [ ! -f "keys/jwt_public.pem" ]; then
    ssh-keygen -f keys/jwt_private.pem -e -m PEM > keys/jwt_public.pem
    chmod 644 keys/jwt_public.pem
    echo -e "${GREEN}✓ JWT public key generated${NC}"
else
    echo -e "${YELLOW}! JWT public key already exists${NC}"
fi

echo ""
echo "Step 5: Creating required directories..."
mkdir -p logs uploads user_data

echo ""
echo "Step 6: Checking environment file..."
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found${NC}"
    echo "  Please create .env from .env.example"
    exit 1
else
    # Check for secrets in .env
    if grep -qE "(AWS_ACCESS_KEY_ID=AKIA|AWS_SECRET_ACCESS_KEY=[A-Za-z0-9+/]{40})" .env 2>/dev/null; then
        echo -e "${RED}✗ WARNING: Found potential secrets in .env file!${NC}"
        echo "  Please remove secrets and use AWS Secrets Manager"
    else
        echo -e "${GREEN}✓ .env file appears clean${NC}"
    fi
fi

echo ""
echo "Step 7: Running security verification..."
if python scripts/verify_security.py; then
    echo -e "${GREEN}✓ Security verification passed${NC}"
else
    echo -e "${YELLOW}! Security verification found issues${NC}"
    echo "  Fix issues before deploying to production"
fi

echo ""
echo "Step 8: Running security scan..."
echo "Running bandit security scan..."
bandit -r backend/ -ll -q || echo -e "${YELLOW}! Some security warnings found${NC}"

echo ""
echo "Step 9: Checking dependencies for vulnerabilities..."
safety check --json 2>/dev/null || echo -e "${YELLOW}! Some dependency vulnerabilities found${NC}"

echo ""
echo "=================================================="
echo -e "${GREEN}Security Setup Complete!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Review any warnings above"
echo "2. Configure AWS Secrets Manager (see DEPLOYMENT_CHECKLIST.md)"
echo "3. Set production environment variables"
echo "4. Run: python scripts/verify_security.py"
echo ""
echo "Pre-commit hooks installed - secrets will be blocked on commit!"
echo ""
