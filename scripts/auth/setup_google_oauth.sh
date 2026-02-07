#!/bin/bash

# Smart AI Tutor - Complete Google OAuth Setup
# Project: Smart Tutor AI (smart-tutor-ai-478221)

set -e

echo "=========================================="
echo "Smart AI Tutor - Google OAuth Setup"
echo "Project: smart-tutor-ai-478221"
echo "=========================================="
echo ""

PROJECT_ID="smart-tutor-ai-478221"

# Step 1: Set project
echo "Step 1: Setting Google Cloud project..."
gcloud config set project "$PROJECT_ID"
echo "✓ Project set to: $PROJECT_ID"
echo ""

# Step 2: Enable required APIs
echo "Step 2: Enabling required Google Cloud APIs..."
echo "This may take a minute..."
gcloud services enable iap.googleapis.com --project="$PROJECT_ID" 2>/dev/null || true
echo "✓ APIs enabled"
echo ""

# Step 3: Open OAuth consent screen setup
echo "Step 3: Opening OAuth Consent Screen setup..."
echo ""
echo "Please complete the following steps in the browser:"
echo ""
echo "1. OAuth Consent Screen Configuration:"
echo "   - User Type: Select 'External' → Click 'CREATE'"
echo ""
echo "2. App Information:"
echo "   - App name: Smart AI Tutor"
echo "   - User support email: liteshperumalla@gmail.com"
echo "   - Developer contact: liteshperumalla@gmail.com"
echo "   - Click 'SAVE AND CONTINUE'"
echo ""
echo "3. Scopes:"
echo "   - Click 'ADD OR REMOVE SCOPES'"
echo "   - Select: openid, email, profile"
echo "   - Click 'UPDATE' → 'SAVE AND CONTINUE'"
echo ""
echo "4. Test Users:"
echo "   - Click 'ADD USERS'"
echo "   - Enter: liteshperumalla@gmail.com"
echo "   - Click 'ADD' → 'SAVE AND CONTINUE'"
echo ""
echo "5. Summary:"
echo "   - Click 'BACK TO DASHBOARD'"
echo ""
echo "Opening browser in 3 seconds..."
sleep 3

open "https://console.cloud.google.com/apis/credentials/consent?project=$PROJECT_ID"

echo ""
read -p "Press ENTER when you've completed the consent screen setup..."

# Step 4: Create OAuth credentials
echo ""
echo "Step 4: Creating OAuth 2.0 credentials..."
echo ""
echo "Opening credentials page..."
sleep 2

open "https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"

echo ""
echo "Please complete these steps:"
echo ""
echo "1. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'"
echo "2. Application type: Select 'Web application'"
echo "3. Name: Smart AI Tutor"
echo "4. Authorized redirect URIs:"
echo "   - Click '+ ADD URI'"
echo "   - Enter: http://localhost:4000/auth/google/callback"
echo "   - Click 'CREATE'"
echo ""
echo "5. IMPORTANT: Copy the Client ID and Client Secret"
echo "   (You'll see a popup with these credentials)"
echo ""
read -p "Press ENTER when you've created the OAuth client..."

echo ""
echo "Step 5: Enter your credentials"
echo ""
read -p "Enter Client ID: " CLIENT_ID
read -p "Enter Client Secret: " CLIENT_SECRET

# Step 6: Update .env
echo ""
echo "Step 6: Updating .env..."

ENV_FILE="/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/.env"
touch "$ENV_FILE"

# Remove existing Google OAuth entries to avoid duplicates
sed -i '' '/^GOOGLE_OAUTH_CLIENT_ID=/d' "$ENV_FILE"
sed -i '' '/^GOOGLE_OAUTH_CLIENT_SECRET=/d' "$ENV_FILE"
sed -i '' '/^GOOGLE_OAUTH_REDIRECT_URI=/d' "$ENV_FILE"
sed -i '' '/^NEXT_PUBLIC_GOOGLE_CLIENT_ID=/d' "$ENV_FILE"
sed -i '' '/^NEXT_PUBLIC_GOOGLE_REDIRECT_URI=/d' "$ENV_FILE"

cat >> "$ENV_FILE" <<EOF
# Google OAuth Configuration
# Project: Smart Tutor AI (smart-tutor-ai-478221)
GOOGLE_OAUTH_CLIENT_ID=$CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET=$CLIENT_SECRET
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:4000/auth/google/callback

# Next.js public env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=$CLIENT_ID
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=http://localhost:4000/auth/google/callback
EOF

echo "✓ .env updated"
echo ""

# Step 7: Verify setup
echo "Step 7: Verifying setup..."
cd "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor"
/opt/homebrew/opt/python@3.11/bin/python3.11 test_oauth.py

echo ""
echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "Your Google OAuth is now configured!"
echo ""
echo "Next steps:"
echo "1. Go to: http://localhost:4000"
echo "2. Click 'Sign in with Google'"
echo "3. Authenticate with your Google account"
echo ""
echo "Your credentials are saved in:"
echo "  .env (excluded from git)"
echo ""
