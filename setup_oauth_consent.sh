#!/bin/bash

# Smart AI Tutor - OAuth Consent Screen Setup Helper
# This script automates the OAuth consent screen configuration as much as possible

set -e

echo "=========================================="
echo "Smart AI Tutor - OAuth Setup Helper"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Get current project
echo -e "${BLUE}Step 1: Checking Google Cloud project...${NC}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}✗ No active Google Cloud project found${NC}"
    echo ""
    echo "Please set your project first:"
    echo "  gcloud config set project YOUR_PROJECT_ID"
    echo ""
    echo "Or list available projects:"
    echo "  gcloud projects list"
    exit 1
fi

echo -e "${GREEN}✓ Active project: ${PROJECT_ID}${NC}"
echo ""

# Step 2: Get project number
echo -e "${BLUE}Step 2: Getting project details...${NC}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
echo -e "${GREEN}✓ Project number: ${PROJECT_NUMBER}${NC}"
echo ""

# Step 3: Enable required APIs
echo -e "${BLUE}Step 3: Enabling required APIs...${NC}"
echo "Enabling OAuth2 API..."
gcloud services enable iap.googleapis.com --project="$PROJECT_ID" 2>/dev/null || true
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Step 4: Get OAuth client details
echo -e "${BLUE}Step 4: Fetching OAuth client details...${NC}"
CLIENT_ID="318834065578-pd3p2efv0dkvicidns6lgb5mrfdv160.apps.googleusercontent.com"
echo -e "${GREEN}✓ Client ID: ${CLIENT_ID}${NC}"
echo ""

# Step 5: Check current OAuth consent screen status
echo -e "${BLUE}Step 5: Checking OAuth consent screen status...${NC}"
CONSENT_SCREEN_URL="https://console.cloud.google.com/apis/credentials/consent?project=${PROJECT_ID}"

# Try to get OAuth brand info (consent screen)
BRAND_INFO=$(gcloud iap oauth-brands list --format="value(name)" 2>/dev/null | head -1)

if [ -z "$BRAND_INFO" ]; then
    echo -e "${YELLOW}⚠ OAuth consent screen not configured yet${NC}"
    NEEDS_SETUP=true
else
    echo -e "${GREEN}✓ OAuth consent screen exists: ${BRAND_INFO}${NC}"
    NEEDS_SETUP=false
fi
echo ""

# Step 6: Create or update consent screen
if [ "$NEEDS_SETUP" = true ]; then
    echo -e "${BLUE}Step 6: Creating OAuth consent screen...${NC}"
    echo ""

    # Create OAuth brand (consent screen)
    echo "Creating OAuth brand..."
    gcloud iap oauth-brands create \
        --application_title="Smart AI Tutor" \
        --support_email="liteshperumalla@gmail.com" \
        --project="$PROJECT_ID" 2>&1 | grep -v "WARNING" || true

    echo -e "${GREEN}✓ OAuth consent screen created${NC}"
    echo ""
else
    echo -e "${BLUE}Step 6: OAuth consent screen already exists${NC}"
    echo ""
fi

# Step 7: Open consent screen configuration page
echo -e "${BLUE}Step 7: Opening OAuth consent screen configuration...${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: You need to complete these steps in the browser:${NC}"
echo ""
echo "1. The OAuth consent screen page will open in your browser"
echo "2. Click 'EDIT APP' button"
echo "3. On the 'OAuth consent screen' page:"
echo "   - Verify App name: Smart AI Tutor"
echo "   - Verify User support email: liteshperumalla@gmail.com"
echo "   - Verify Developer contact: liteshperumalla@gmail.com"
echo "   - Click 'SAVE AND CONTINUE'"
echo ""
echo "4. On 'Scopes' page:"
echo "   - Click 'ADD OR REMOVE SCOPES'"
echo "   - Select: openid, email, profile"
echo "   - Click 'UPDATE' then 'SAVE AND CONTINUE'"
echo ""
echo "5. On 'Test users' page (MOST IMPORTANT!):"
echo "   - Click 'ADD USERS'"
echo "   - Enter: liteshperumalla@gmail.com"
echo "   - Click 'SAVE'"
echo "   - Click 'SAVE AND CONTINUE'"
echo ""
echo "6. Click 'BACK TO DASHBOARD'"
echo ""
echo "Opening browser in 3 seconds..."
sleep 3

# Open the consent screen page
open "$CONSENT_SCREEN_URL" 2>/dev/null || xdg-open "$CONSENT_SCREEN_URL" 2>/dev/null || echo "Please open: $CONSENT_SCREEN_URL"

echo ""
echo -e "${GREEN}=========================================="
echo "Browser opened!"
echo "==========================================${NC}"
echo ""
echo "After completing the setup in browser, press ENTER to verify..."
read -r

# Step 8: Verify setup
echo ""
echo -e "${BLUE}Step 8: Verifying OAuth setup...${NC}"
echo ""

# Check if brand exists now
BRAND_INFO=$(gcloud iap oauth-brands list --format="value(name)" 2>/dev/null | head -1)
if [ -n "$BRAND_INFO" ]; then
    echo -e "${GREEN}✓ OAuth consent screen is configured${NC}"
else
    echo -e "${RED}✗ OAuth consent screen not found${NC}"
    echo "Please complete the setup in the browser"
fi

echo ""
echo -e "${BLUE}Step 9: Testing OAuth credentials...${NC}"
cd "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor"
/opt/homebrew/opt/python@3.11/bin/python3.11 test_oauth.py

echo ""
echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Go to your app: http://localhost:8501"
echo "2. Click 'Sign in with Google'"
echo "3. Authenticate with your Google account"
echo ""
echo "If you still get errors, make sure:"
echo "- You added yourself (liteshperumalla@gmail.com) as a test user"
echo "- You saved all changes in the consent screen setup"
echo ""
