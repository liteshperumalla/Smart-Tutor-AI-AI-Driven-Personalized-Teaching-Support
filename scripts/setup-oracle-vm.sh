#!/bin/bash
# =============================================================================
# Oracle Cloud ARM VM Setup Script
# Covers Tasks 12–14: Install Docker, clone repo, configure Nginx + SSL
#
# Usage (from your LOCAL machine):
#   chmod +x scripts/setup-oracle-vm.sh
#   VM_IP=<YOUR_ORACLE_IP> ./scripts/setup-oracle-vm.sh
#
# Or step-by-step after SSHing in:
#   ssh ubuntu@<YOUR_ORACLE_IP>
#   bash -c "$(curl -fsSL <raw-github-url-of-this-script>)"
# =============================================================================

set -euo pipefail

DOMAIN="${DOMAIN:-}"          # optional: set to enable Let's Encrypt TLS
REPO_URL="${REPO_URL:-}"      # required: git clone URL of this repo
VM_IP="${VM_IP:-$(curl -s ifconfig.me)}"

echo "==> [1/6] System update & base packages"
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y \
    docker.io docker-compose-plugin \
    git curl nginx certbot python3-certbot-nginx \
    netfilter-persistent iptables-persistent ufw

echo "==> [2/6] Enable Docker + add ubuntu to docker group"
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
# Note: 'newgrp docker' affects only interactive shells; log out/in or use 'sg docker'

echo "==> [3/6] Open firewall ports (Oracle uses iptables, not ufw by default)"
sudo iptables -I INPUT -p tcp --dport 80  -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

echo "==> [4/6] Clone repository"
if [ -z "$REPO_URL" ]; then
  echo "ERROR: REPO_URL not set. Run: REPO_URL=<url> ./setup-oracle-vm.sh"
  exit 1
fi
if [ ! -d "$HOME/smart-tutor" ]; then
  git clone "$REPO_URL" "$HOME/smart-tutor"
else
  echo "  (repo already cloned, pulling latest)"
  git -C "$HOME/smart-tutor" pull
fi
cd "$HOME/smart-tutor"

echo "==> [5/6] Create .env from example (manual edit required)"
if [ ! -f .env ]; then
  cp .env.example .env 2>/dev/null || touch .env
  # Inject random secrets
  JWT_SECRET=$(openssl rand -hex 32)
  PG_PASS=$(openssl rand -hex 16)
  REDIS_PASS=$(openssl rand -hex 16)
  sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env
  sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PG_PASS|" .env
  sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASS|" .env
  sed -i "s|ENVIRONMENT=.*|ENVIRONMENT=production|" .env
  sed -i "s|DEBUG=.*|DEBUG=false|" .env
  echo ""
  echo "*** IMPORTANT: Edit .env to add your AWS credentials, Vercel URL for CORS, etc. ***"
  echo "    nano $HOME/smart-tutor/.env"
fi

echo "==> [5b/6] Start Docker Compose stack"
sg docker -c "docker compose up -d"
echo "  Waiting 15s for services to start..."
sleep 15
sg docker -c "docker compose ps"

echo "==> [6/6] Configure Nginx reverse proxy"
NGINX_CONF="/etc/nginx/sites-available/smart-tutor"
NGINX_LINK="/etc/nginx/sites-enabled/smart-tutor"

cat > /tmp/smart-tutor-nginx.conf << NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN:-$VM_IP};

    # Streaming / SSE support — disable buffering globally for /api/
    location /api/ {
        proxy_pass         http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_buffering    off;
        proxy_read_timeout 300s;
    }

    location /admin {
        proxy_pass         http://localhost:8000;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
    }

    location / {
        proxy_pass         http://localhost:4000;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        # WebSocket support (for future use)
        proxy_set_header   Upgrade           \$http_upgrade;
        proxy_set_header   Connection        "upgrade";
    }
}
NGINXEOF

sudo cp /tmp/smart-tutor-nginx.conf "$NGINX_CONF"
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf "$NGINX_CONF" "$NGINX_LINK"
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx

if [ -n "$DOMAIN" ]; then
  echo ""
  echo "==> [6b] Obtaining Let's Encrypt certificate for $DOMAIN"
  sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"
else
  echo ""
  echo "NOTE: No DOMAIN set. Running on HTTP only (IP: $VM_IP)."
  echo "  To add TLS later: DOMAIN=yourdomain.com sudo certbot --nginx -d yourdomain.com"
fi

echo ""
echo "============================================================"
echo " Setup complete! Checklist:"
echo "   [ ] Edit .env: add AWS keys, Vercel CORS URL, etc."
echo "   [ ] docker compose restart backend  (after editing .env)"
echo "   [ ] curl http://$VM_IP/api/v1/health"
echo "   [ ] In Oracle Console: add Security List ingress rules"
echo "       for TCP 80 and TCP 443 (VCN -> Subnets -> Security Lists)"
echo "============================================================"
