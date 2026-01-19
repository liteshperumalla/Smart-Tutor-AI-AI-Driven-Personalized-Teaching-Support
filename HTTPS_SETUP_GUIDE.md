# HTTPS Setup Guide

## Overview

This guide explains how to enable HTTPS for the Smart AI Tutor application in production.

---

## Prerequisites

1. **Domain Name**: You need a registered domain (e.g., `smartaitutor.com`)
2. **SSL Certificate**: Obtain an SSL/TLS certificate
3. **Load Balancer or Reverse Proxy**: To handle HTTPS termination

---

## Option 1: AWS Application Load Balancer (Recommended)

### Step 1: Request SSL Certificate

```bash
# Request certificate via AWS Certificate Manager
aws acm request-certificate \
  --domain-name smartaitutor.com \
  --subject-alternative-names www.smartaitutor.com app.smartaitutor.com \
  --validation-method DNS \
  --region us-east-1
```

### Step 2: Validate Certificate

1. Go to AWS Certificate Manager console
2. Click on the certificate
3. Create DNS records as instructed (CNAME records)
4. Wait for validation (usually 5-30 minutes)

### Step 3: Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name smart-tutor-alb \
  --subnets subnet-xxxxx subnet-yyyyy \
  --security-groups sg-xxxxx \
  --scheme internet-facing \
  --type application \
  --region us-east-1

# Create target group
aws elbv2 create-target-group \
  --name smart-tutor-backend \
  --protocol HTTP \
  --port 8010 \
  --vpc-id vpc-xxxxx \
  --health-check-path /health \
  --region us-east-1

# Create HTTPS listener
aws elbv2 create-listener \
  --load-balancer-arn <ALB_ARN> \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=<CERTIFICATE_ARN> \
  --default-actions Type=forward,TargetGroupArn=<TARGET_GROUP_ARN>

# Create HTTP to HTTPS redirect listener
aws elbv2 create-listener \
  --load-balancer-arn <ALB_ARN> \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=redirect,RedirectConfig='{Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'
```

### Step 4: Update DNS

Point your domain to the ALB:

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers \
  --names smart-tutor-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text

# Create CNAME record in Route53 or your DNS provider
# smartaitutor.com -> smart-tutor-alb-xxxxx.us-east-1.elb.amazonaws.com
```

### Step 5: Enable HTTPS Enforcement in Application

Update `.env`:

```bash
ENFORCE_HTTPS=true
CORS_ALLOWED_ORIGINS=https://smartaitutor.com,https://app.smartaitutor.com
CORS_ALLOW_LOCALHOST=false
```

---

## Option 2: Nginx Reverse Proxy with Let's Encrypt

### Step 1: Install Nginx

```bash
# On EC2 instance
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx -y
```

### Step 2: Configure Nginx

Create `/etc/nginx/sites-available/smartaitutor`:

```nginx
server {
    listen 80;
    server_name smartaitutor.com www.smartaitutor.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name smartaitutor.com www.smartaitutor.com;

    # SSL configuration will be added by certbot

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:4000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/smartaitutor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 3: Obtain SSL Certificate

```bash
sudo certbot --nginx -d smartaitutor.com -d www.smartaitutor.com
```

Follow the prompts. Certbot will automatically:
- Obtain the certificate
- Update Nginx configuration
- Set up auto-renewal

### Step 4: Enable HTTPS Enforcement

Update `.env`:

```bash
ENFORCE_HTTPS=true
CORS_ALLOWED_ORIGINS=https://smartaitutor.com,https://www.smartaitutor.com
CORS_ALLOW_LOCALHOST=false
```

---

## Option 3: Cloudflare (Easiest)

### Step 1: Add Domain to Cloudflare

1. Go to https://cloudflare.com
2. Add your domain
3. Update nameservers at your domain registrar

### Step 2: Configure DNS

In Cloudflare DNS:
- Add A record: `@` → Your server IP
- Add A record: `www` → Your server IP
- Add A record: `app` → Your server IP

### Step 3: Enable SSL/TLS

In Cloudflare SSL/TLS settings:
- SSL/TLS encryption mode: **Full (strict)** or **Flexible**
- Enable "Always Use HTTPS"
- Enable "Automatic HTTPS Rewrites"

### Step 4: Update Application

Update `.env`:

```bash
ENFORCE_HTTPS=true
CORS_ALLOWED_ORIGINS=https://smartaitutor.com,https://app.smartaitutor.com
CORS_ALLOW_LOCALHOST=false
```

---

## Current Configuration (Local Testing)

For local testing, HTTPS enforcement is **disabled**:

```bash
# .env
ENFORCE_HTTPS=false
CORS_ALLOW_LOCALHOST=true
```

This allows the application to run on `http://localhost:8010` during development.

---

## Verifying HTTPS Configuration

### Test SSL Certificate

```bash
# Check certificate
openssl s_client -connect smartaitutor.com:443 -servername smartaitutor.com

# Test with curl
curl -I https://smartaitutor.com

# Verify redirect from HTTP to HTTPS
curl -I http://smartaitutor.com
```

### Test Application

1. Access `https://smartaitutor.com` in browser
2. Verify padlock icon appears
3. Check browser console for mixed content warnings
4. Test API calls from frontend

---

## Security Best Practices

### 1. Strong SSL Configuration

```nginx
# In Nginx config
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;

# Enable HSTS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### 2. Auto-Renewal for Let's Encrypt

```bash
# Test renewal
sudo certbot renew --dry-run

# Renewal runs automatically via cron
# Check: sudo systemctl status certbot.timer
```

### 3. Monitor Certificate Expiration

Set up CloudWatch alarm or use services like:
- SSL Labs: https://www.ssllabs.com/ssltest/
- Certificate monitoring services

---

## Troubleshooting

### Mixed Content Errors

If you see "Mixed Content" warnings:

1. Check all API calls use `https://`
2. Update frontend API base URL
3. Ensure all external resources use HTTPS

### Certificate Validation Failed

1. Verify DNS is pointing to correct server
2. Check firewall allows port 80 (for validation)
3. Ensure certificate ARN is correct (for ALB)

### CORS Errors After Enabling HTTPS

1. Update `CORS_ALLOWED_ORIGINS` to include `https://` URLs
2. Restart backend after `.env` changes
3. Clear browser cache

---

## Cost Considerations

| Method | Cost |
|--------|------|
| AWS Certificate Manager | Free |
| Application Load Balancer | ~$16/month + $0.008/LCU-hour |
| Let's Encrypt (Certbot) | Free |
| Cloudflare Free Plan | Free (with limitations) |
| Cloudflare Pro | $20/month |

---

## Deployment Checklist

Before enabling HTTPS in production:

- [ ] Domain registered and DNS configured
- [ ] SSL certificate obtained and validated
- [ ] Load balancer or reverse proxy configured
- [ ] HTTPS listener created (port 443)
- [ ] HTTP to HTTPS redirect enabled (port 80)
- [ ] `ENFORCE_HTTPS=true` in `.env`
- [ ] `CORS_ALLOWED_ORIGINS` updated with `https://` URLs
- [ ] `CORS_ALLOW_LOCALHOST=false` in production
- [ ] Certificate auto-renewal configured
- [ ] Monitoring set up for certificate expiration
- [ ] Application tested with HTTPS
- [ ] Browser console checked for mixed content
- [ ] API calls verified working over HTTPS

---

## Current Status

✅ **HTTPS Configuration Code**: Ready in `backend/api/main.py`
✅ **Environment Variables**: Configured in `.env`
⚠️ **HTTPS Enforcement**: Disabled (waiting for domain/certificate)
⚠️ **SSL Certificate**: Not obtained yet
⚠️ **Production Domain**: Not configured yet

**To enable HTTPS**: Follow one of the options above, then set `ENFORCE_HTTPS=true` in `.env`.

---

**Last Updated**: 2025-12-19
**Document**: HTTPS_SETUP_GUIDE.md
