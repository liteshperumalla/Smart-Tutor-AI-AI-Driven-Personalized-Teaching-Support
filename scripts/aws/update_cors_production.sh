#!/bin/bash
set -e

# Update CORS settings for production deployment

echo "🌐 Updating CORS Configuration for Production..."
echo ""

# Prompt for production domain
echo "📝 Enter your production domain(s):"
echo "   Example: https://smarttutor.example.com"
echo "   Multiple domains: comma-separated"
read -p "Domain(s): " PRODUCTION_DOMAINS

if [ -z "$PRODUCTION_DOMAINS" ]; then
  echo "❌ No domain specified. Exiting."
  exit 1
fi

echo ""
echo "🔧 Updating .env file..."

# Update .env file
if [ -f ".env" ]; then
  # Backup current .env
  cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
  echo "✓ Backed up current .env"

  # Update CORS_ALLOWED_ORIGINS
  if grep -q "^CORS_ALLOWED_ORIGINS=" .env; then
    sed -i.bak "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=${PRODUCTION_DOMAINS}|" .env
    echo "✓ Updated CORS_ALLOWED_ORIGINS"
  else
    echo "CORS_ALLOWED_ORIGINS=${PRODUCTION_DOMAINS}" >> .env
    echo "✓ Added CORS_ALLOWED_ORIGINS"
  fi

  # Disable localhost in production
  if grep -q "^CORS_ALLOW_LOCALHOST=" .env; then
    sed -i.bak "s|^CORS_ALLOW_LOCALHOST=.*|CORS_ALLOW_LOCALHOST=false|" .env
    echo "✓ Disabled CORS_ALLOW_LOCALHOST"
  else
    echo "CORS_ALLOW_LOCALHOST=false" >> .env
    echo "✓ Added CORS_ALLOW_LOCALHOST=false"
  fi

  # Clean up backup files
  rm -f .env.bak

else
  echo "⚠️  .env file not found. Creating from .env.example..."
  cp .env.example .env
  echo "CORS_ALLOWED_ORIGINS=${PRODUCTION_DOMAINS}" >> .env
  echo "CORS_ALLOW_LOCALHOST=false" >> .env
fi

echo ""
echo "📋 Current CORS Configuration:"
grep -E "^CORS_" .env || echo "No CORS settings found"

echo ""
echo "✅ CORS configuration updated!"
echo ""
echo "📝 Summary:"
echo "   Allowed Origins: $PRODUCTION_DOMAINS"
echo "   Localhost Access: Disabled"
echo ""
echo "⚠️  Important:"
echo "   1. Restart backend service to apply changes:"
echo "      ./manage_services.sh restart backend"
echo ""
echo "   2. Verify CORS in browser console after deployment"
echo ""
echo "   3. Test with:"
echo "      curl -H 'Origin: ${PRODUCTION_DOMAINS%,*}' \\"
echo "           -H 'Access-Control-Request-Method: POST' \\"
echo "           -X OPTIONS https://your-api.com/api/v1/auth/login"
echo ""
echo "🔒 Security Checklist:"
echo "   ✓ CORS restricted to production domains"
echo "   ✓ Localhost access disabled"
echo "   ✓ HTTPS enforced (check ENFORCE_HTTPS=true)"
echo "   ✓ Credentials included (check CORS settings in backend)"
