# Testing & Oracle Cloud Deployment — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete risk-first testing pass (security → APIs → frontend → E2E) then deploy to Oracle Cloud ARM + Vercel.

**Architecture:** pytest + FastAPI TestClient for backend, Jest/RTL for frontend components, Playwright for E2E. All phases run in order — fix failures before advancing. Deployment uses Docker Compose on Oracle Cloud ARM VM (always free, 24GB RAM) with Vercel for Next.js.

**Tech Stack:** pytest, FastAPI TestClient, Jest, React Testing Library, Playwright, Docker Compose, Nginx, Certbot, Vercel CLI

---

## Phase 1 — Security & Authentication Tests

### Task 1: Expand `test_auth.py` — JWT blacklist after logout

**Files:**
- Modify: `backend/tests/test_auth.py`

**Step 1: Add the test**

Add this class to `backend/tests/test_auth.py`:

```python
class TestJWTSecurity:
    """Test JWT security edge cases"""

    def test_blacklisted_token_rejected_after_logout(self, test_client, test_user):
        """Token used after logout must return 401"""
        # Login
        login = test_client.post("/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Logout
        test_client.post("/auth/logout", headers=headers)

        # Try using the same token — must be rejected
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 401

    def test_expired_token_rejected(self, test_client):
        """A manually crafted expired token must return 401"""
        from jose import jwt
        from datetime import datetime, timedelta, timezone
        expired_token = jwt.encode(
            {
                "sub": "testuser",
                "email": "test@example.com",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "iss": "smart-tutor",
                "aud": "smart-tutor-api",
                "type": "access",
                "jti": "test-expired-jti"
            },
            "test-secret-key-for-testing-only",
            algorithm="HS256"
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 401

    def test_malformed_token_rejected(self, test_client):
        """Garbage token string must return 401, not 500"""
        headers = {"Authorization": "Bearer not.a.valid.jwt.at.all"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 401

    def test_token_type_mismatch_rejected(self, test_client, test_user):
        """Using a refresh token as an access token must be rejected"""
        login = test_client.post("/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        refresh_token = login.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {refresh_token}"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 401
```

**Step 2: Run and verify**

```bash
cd "backend" && python -m pytest tests/test_auth.py::TestJWTSecurity -v
```

Expected: All 4 tests PASS.

**Step 3: Commit**

```bash
git add backend/tests/test_auth.py
git commit -m "test: add JWT security edge cases (blacklist, expiry, malformed, type mismatch)"
```

---

### Task 2: Create `test_security.py` — Admin lockdown + CSRF + rate limiting

**Files:**
- Create: `backend/tests/test_security.py`

**Step 1: Create the file**

```python
"""
Security Tests
Tests for admin lockdown, CSRF protection, rate limiting, and input validation.
"""

import pytest


class TestAdminLockdown:
    """Admin routes must be inaccessible to regular users"""

    def test_admin_users_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/users"""
        response = test_client.get("/admin/users", headers=auth_headers)
        assert response.status_code == 403

    def test_admin_llmops_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/llmops"""
        response = test_client.get("/admin/llmops", headers=auth_headers)
        assert response.status_code == 403

    def test_admin_prompts_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/prompts"""
        response = test_client.get("/admin/prompts/system_prompt", headers=auth_headers)
        assert response.status_code == 403

    def test_admin_requires_auth(self, test_client):
        """Unauthenticated request to admin route must return 401"""
        response = test_client.get("/admin/users")
        assert response.status_code in (401, 403)

    def test_admin_agent_metrics_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/agent-metrics"""
        response = test_client.get("/admin/agent-metrics", headers=auth_headers)
        assert response.status_code == 403


class TestInputValidation:
    """Malformed inputs must be rejected cleanly (no 500s)"""

    def test_login_sql_injection_probe(self, test_client):
        """SQL injection in username must return 401/422, not 500"""
        response = test_client.post("/auth/login", json={
            "username": "' OR '1'='1",
            "password": "anything"
        })
        assert response.status_code in (401, 422)

    def test_login_oversized_payload(self, test_client):
        """Extremely long username must return 422, not 500"""
        response = test_client.post("/auth/login", json={
            "username": "A" * 10000,
            "password": "password"
        })
        assert response.status_code in (401, 422)

    def test_signup_xss_probe(self, test_client):
        """XSS payload in full_name must be accepted or sanitized, not crash"""
        response = test_client.post("/auth/signup", json={
            "username": "xsstest123",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "email": "xss@example.com",
            "full_name": "<script>alert('xss')</script>"
        })
        # Either accepted (sanitized on display) or rejected — not 500
        assert response.status_code in (200, 400, 422)

    def test_protected_route_no_auth_header(self, test_client):
        """Missing Authorization header must return 401, not 500"""
        response = test_client.get("/chat/sessions")
        assert response.status_code == 401

    def test_protected_route_malformed_auth_header(self, test_client):
        """Malformed Authorization header must return 401, not 500"""
        response = test_client.get("/chat/sessions", headers={"Authorization": "NotBearer token"})
        assert response.status_code == 401
```

**Step 2: Run and verify**

```bash
cd "backend" && python -m pytest tests/test_security.py -v
```

Expected: All tests PASS. If an admin test returns 401 instead of 403, check `backend/api/dependencies.py` — the dependency may check auth before role.

**Step 3: Commit**

```bash
git add backend/tests/test_security.py
git commit -m "test: add admin lockdown, input validation, and auth edge case security tests"
```

---

## Phase 2 — Core API Tests

### Task 3: Expand `test_chat.py` — Session isolation + streaming

**Files:**
- Modify: `backend/tests/test_chat.py`

**Step 1: Add session isolation tests**

Append to `backend/tests/test_chat.py`:

```python
class TestSessionIsolation:
    """Users must not access each other's sessions"""

    def test_user_cannot_access_other_users_session(self, test_client, auth_headers, auth_service):
        """User A's session must not be accessible by User B"""
        from backend.database import get_user_db

        # Create user B
        user_db = get_user_db()
        if user_db.user_exists("userb_isolation"):
            user_db.delete_user("userb_isolation")
        auth_service.register_user(
            username="userb_isolation",
            password="SecurePass123!",
            confirm_password="SecurePass123!",
            email="userb_isolation@example.com"
        )

        # User A creates a session
        session_resp = test_client.post("/chat/sessions", headers=auth_headers)
        assert session_resp.status_code == 200
        session_id = session_resp.json()["session"]["id"]

        # User B logs in
        login_b = test_client.post("/auth/login", json={
            "username": "userb_isolation",
            "password": "SecurePass123!"
        })
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B tries to access User A's session
        response = test_client.get(f"/chat/sessions/{session_id}", headers=headers_b)
        assert response.status_code in (403, 404)

        # Cleanup
        user_db.delete_user("userb_isolation")

    def test_invalid_session_id_returns_404(self, test_client, auth_headers):
        """Non-existent session ID must return 404, not 500"""
        response = test_client.get("/chat/sessions/nonexistent-session-id-xyz", headers=auth_headers)
        assert response.status_code == 404
```

**Step 2: Run and verify**

```bash
cd "backend" && python -m pytest tests/test_chat.py -v
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add backend/tests/test_chat.py
git commit -m "test: add chat session isolation and invalid session ID tests"
```

---

### Task 4: Create `test_files.py` — File upload validation

**Files:**
- Create: `backend/tests/test_files.py`

**Step 1: Create the file**

```python
"""
File Upload Tests
Tests for file upload validation, type checking, and size limits.
"""

import pytest
import io


class TestFileUpload:
    """Test file upload endpoint validation"""

    def test_valid_pdf_upload(self, test_client, auth_headers):
        """Valid PDF file upload must succeed"""
        # Minimal valid PDF header
        pdf_content = b"%PDF-1.4\n%Test PDF content for testing purposes only"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        response = test_client.post("/chat/upload", headers=auth_headers, files=files)
        # Accept 200 (success) or 400 (if PDF parsing requires real content) — not 500
        assert response.status_code in (200, 400)

    def test_invalid_file_type_rejected(self, test_client, auth_headers):
        """Non-PDF/non-allowed file type must return 400"""
        files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
        response = test_client.post("/chat/upload", headers=auth_headers, files=files)
        assert response.status_code == 400

    def test_empty_file_rejected(self, test_client, auth_headers):
        """Empty file must return 400"""
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        response = test_client.post("/chat/upload", headers=auth_headers, files=files)
        assert response.status_code == 400

    def test_upload_requires_auth(self, test_client):
        """File upload without auth must return 401"""
        files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
        response = test_client.post("/chat/upload", files=files)
        assert response.status_code == 401
```

**Step 2: Run and verify**

```bash
cd "backend" && python -m pytest tests/test_files.py -v
```

If `/chat/upload` does not exist, check `backend/api/routes/chat.py` for the actual upload endpoint path and update accordingly.

**Step 3: Commit**

```bash
git add backend/tests/test_files.py
git commit -m "test: add file upload validation tests (type, size, auth)"
```

---

### Task 5: Create `test_quiz.py` — Quiz CRUD + auth

**Files:**
- Create: `backend/tests/test_quiz.py`

**Step 1: Create the file**

```python
"""
Quiz Tests
Tests for quiz generation and submission.
"""

import pytest


class TestQuizEndpoints:
    """Test quiz API endpoints"""

    def test_quiz_requires_auth(self, test_client):
        """Quiz endpoint without auth must return 401"""
        response = test_client.post("/quiz/generate", json={
            "folders": ["Module 1"],
            "num_questions": 5
        })
        assert response.status_code == 401

    def test_generate_quiz_with_auth(self, test_client, auth_headers):
        """Authenticated user can request quiz generation"""
        response = test_client.post("/quiz/generate", headers=auth_headers, json={
            "folders": ["Module 1"],
            "num_questions": 3
        })
        # Accept 200 (generated) or 422 (folders not found) — not 500
        assert response.status_code in (200, 400, 422)

    def test_get_quiz_results_requires_auth(self, test_client):
        """Quiz results without auth must return 401"""
        response = test_client.get("/quiz/results")
        assert response.status_code == 401

    def test_get_quiz_results_with_auth(self, test_client, auth_headers):
        """Authenticated user can retrieve their quiz results"""
        response = test_client.get("/quiz/results", headers=auth_headers)
        assert response.status_code in (200, 404)
```

**Step 2: Run and verify**

```bash
cd "backend" && python -m pytest tests/test_quiz.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/test_quiz.py
git commit -m "test: add quiz auth and endpoint tests"
```

---

### Task 6: Create `test_profile.py` — Profile isolation

**Files:**
- Create: `backend/tests/test_profile.py`

**Step 1: Create the file**

```python
"""
Profile Tests
Tests for user profile access and update.
"""

import pytest


class TestProfileEndpoints:
    """Test user profile endpoints"""

    def test_get_profile_requires_auth(self, test_client):
        """Profile endpoint without auth must return 401"""
        response = test_client.get("/profile")
        assert response.status_code == 401

    def test_get_own_profile(self, test_client, auth_headers):
        """Authenticated user can fetch their own profile"""
        response = test_client.get("/profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "username" in data or "user" in data

    def test_update_profile_requires_auth(self, test_client):
        """Profile update without auth must return 401"""
        response = test_client.put("/profile", json={"full_name": "Hacker"})
        assert response.status_code == 401

    def test_update_own_profile(self, test_client, auth_headers):
        """Authenticated user can update their own profile"""
        response = test_client.put("/profile", headers=auth_headers, json={
            "full_name": "Updated Name"
        })
        assert response.status_code in (200, 204)
```

**Step 2: Run and verify**

```bash
cd "backend" && python -m pytest tests/test_profile.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/test_profile.py
git commit -m "test: add profile access and update tests"
```

---

### Task 7: Run full backend test suite — fix any failures

**Step 1: Run all backend tests**

```bash
cd "backend" && python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/pytest_results.txt
```

**Step 2: Review failures**

```bash
grep -E "FAILED|ERROR" /tmp/pytest_results.txt
```

**Step 3: Fix any failures**

For each failure, read the traceback, identify root cause, fix the code or the test (prefer fixing code if it's a real bug), then re-run that specific test:

```bash
cd "backend" && python -m pytest tests/test_security.py::TestAdminLockdown::test_admin_users_requires_admin_role -v
```

**Step 4: Commit all fixes**

```bash
git add -p  # stage only what you fixed
git commit -m "fix: resolve failing backend tests from full suite run"
```

---

## Phase 3 — Frontend Tests

### Task 8: Add frontend component tests

**Files:**
- Create: `frontend/src/components/__tests__/auth-form.test.tsx`

**Step 1: Check if Jest is configured**

```bash
cd frontend && cat package.json | grep -E '"jest|"test'
```

If `jest` is not configured, check for `vitest` or `@testing-library/react`. Use whichever is present.

**Step 2: Create auth form test**

Create `frontend/src/components/__tests__/auth-form.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'

// Import the login form component — adjust path to match actual file
// Run: find frontend/src -name "*.tsx" | xargs grep -l "username.*password" | head -5
// to find the right component
import LoginForm from '../LoginForm'  // adjust path as needed

describe('LoginForm', () => {
  it('renders username and password fields', () => {
    render(<LoginForm />)
    expect(screen.getByPlaceholderText(/username/i) || screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/password/i) || screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('shows validation error when submitted empty', async () => {
    render(<LoginForm />)
    fireEvent.click(screen.getByRole('button', { name: /sign in|log in|login/i }))
    await waitFor(() => {
      expect(screen.getByText(/required|enter.*username/i)).toBeInTheDocument()
    })
  })
})
```

**Note:** The component path `LoginForm` is a placeholder. Before running, find the actual login component:

```bash
find frontend/src -name "*.tsx" | xargs grep -l "username" 2>/dev/null | head -5
```

Update the import accordingly.

**Step 3: Run frontend tests**

```bash
cd frontend && npm test -- --watchAll=false 2>&1 | tee /tmp/frontend_test_results.txt
```

**Step 4: Commit**

```bash
git add frontend/src/components/__tests__/
git commit -m "test: add auth form component tests"
```

---

## Phase 4 — E2E Tests (Playwright)

### Task 9: Expand E2E auth + chat tests

**Files:**
- Modify: `e2e/tests/auth.spec.ts`
- Modify: `e2e/tests/chat.spec.ts`

**Step 1: Add logout test to `auth.spec.ts`**

Append to `e2e/tests/auth.spec.ts`:

```typescript
test('should logout and redirect to login page', async ({ page }) => {
  // Login first
  await page.goto('/login')
  await page.fill('input[name="username"]', 'testuser')
  await page.fill('input[name="password"]', 'TestPass123!')
  await page.click('button[type="submit"]')
  await page.waitForURL('/')

  // Logout
  await page.click('[data-testid="logout-button"], text=Logout, text=Sign out')
  await expect(page).toHaveURL(/.*login/)
})

test('should redirect unauthenticated user from protected route', async ({ page }) => {
  await page.goto('/chat')
  await expect(page).toHaveURL(/.*login/)
})
```

**Step 2: Add streaming response test to `chat.spec.ts`**

Append to `e2e/tests/chat.spec.ts`:

```typescript
test('should receive streaming response and show sources', async ({ page }) => {
  await page.goto('/chat')

  await page.fill('textarea[placeholder*="Ask"], textarea[placeholder*="ask"]', 'What is supervised learning?')
  await page.keyboard.press('Enter')

  // Wait for response to start streaming
  await expect(page.locator('[class*="assistant"], [data-role="assistant"]')).toBeVisible({ timeout: 30000 })

  // Check page has content (streaming completed)
  await page.waitForTimeout(3000)
  const responseText = await page.locator('[class*="assistant"], [data-role="assistant"]').first().textContent()
  expect(responseText?.length).toBeGreaterThan(20)
})
```

**Step 3: Create `e2e/tests/admin.spec.ts`**

```typescript
import { test, expect } from '@playwright/test'

test.describe('Admin Access Control', () => {
  test('non-admin user cannot access admin panel', async ({ page }) => {
    // Login as regular user
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')

    // Try to navigate to admin
    await page.goto('/admin')

    // Should be redirected or shown access denied
    const url = page.url()
    const isRedirected = !url.includes('/admin') || url.includes('/login')
    const hasAccessDenied = await page.locator('text=Access Denied, text=Forbidden, text=403').isVisible()

    expect(isRedirected || hasAccessDenied).toBeTruthy()
  })
})
```

**Step 4: Run E2E tests (requires running app)**

First ensure the app is running:

```bash
docker compose up -d backend frontend
```

Then run E2E tests:

```bash
cd e2e && npx playwright test --reporter=list 2>&1 | tee /tmp/e2e_results.txt
```

**Step 5: Commit**

```bash
git add e2e/tests/
git commit -m "test: expand E2E tests for logout, streaming, and admin access control"
```

---

### Task 10: Full test run — verify everything green

**Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: 0 failures.

**Step 2: Run frontend tests**

```bash
cd frontend && npm test -- --watchAll=false
```

Expected: 0 failures.

**Step 3: Run E2E tests**

```bash
cd e2e && npx playwright test --reporter=list
```

Expected: All pass or known-skip for unavailable features.

**Step 4: Commit final state**

```bash
git add .
git commit -m "test: all phases green — ready for Oracle Cloud deployment"
```

---

## Phase 5 — Oracle Cloud Deployment

### Task 11: Provision Oracle Cloud ARM VM

**Step 1: Log in to Oracle Cloud Console**

Go to https://cloud.oracle.com and sign in.

**Step 2: Create VM instance**

Navigate to: Compute → Instances → Create Instance

Settings:
- **Name**: `smart-tutor-prod`
- **Image**: Ubuntu 22.04 (Canonical)
- **Shape**: VM.Standard.A1.Flex (ARM) — select **4 OCPUs, 24GB RAM** (Always Free)
- **SSH key**: Add your public key (`~/.ssh/id_rsa.pub` or generate new)
- **Boot volume**: 50GB (free tier includes 200GB total)

Click **Create**.

**Step 3: Note the public IP**

Save the public IP address shown on the instance page. You'll use it throughout.

---

### Task 12: Configure VM — Docker + security

**Step 1: SSH into the VM**

```bash
ssh ubuntu@<YOUR_ORACLE_VM_IP>
```

**Step 2: Update system + install Docker**

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git curl nginx certbot python3-certbot-nginx
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
newgrp docker
```

**Step 3: Open required firewall ports in Oracle Cloud**

In Oracle Console → Networking → Virtual Cloud Networks → Security Lists, add ingress rules:
- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 22 (SSH — should already exist)

Also run on the VM itself:

```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

### Task 13: Deploy application

**Step 1: Clone the repo on the VM**

```bash
git clone <YOUR_REPO_URL> ~/smart-tutor
cd ~/smart-tutor
```

**Step 2: Create production `.env`**

```bash
cp .env.example .env  # or create from scratch
nano .env
```

Update these values (generate strong random secrets):

```bash
ENVIRONMENT=production
DEBUG=false
JWT_SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
REDIS_PASSWORD=$(openssl rand -hex 16)
CORS_ORIGINS=["https://your-app.vercel.app"]
# Keep existing AWS credentials (DynamoDB, S3, Bedrock)
```

**Step 3: Start the stack**

```bash
docker compose up -d
```

**Step 4: Verify all containers are running**

```bash
docker compose ps
```

Expected: backend, frontend, postgres, redis, neo4j all `Up`.

---

### Task 14: Configure Nginx reverse proxy + SSL

**Step 1: Create Nginx config**

```bash
sudo nano /etc/nginx/sites-available/smart-tutor
```

Paste:

```nginx
server {
    listen 80;
    server_name <YOUR_DOMAIN_OR_IP>;

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # SSE / streaming support
        proxy_buffering off;
        proxy_read_timeout 300s;
    }

    location /admin {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://localhost:4000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Step 2: Enable and test**

```bash
sudo ln -s /etc/nginx/sites-available/smart-tutor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Step 3: Add SSL with Let's Encrypt (requires a domain name)**

If you have a domain pointed at the Oracle IP:

```bash
sudo certbot --nginx -d yourdomain.com
```

If using IP only (demo), skip SSL for now.

---

### Task 15: Deploy frontend to Vercel

**Step 1: Install Vercel CLI**

```bash
npm install -g vercel
```

**Step 2: Login and link**

```bash
cd frontend
vercel login
vercel link
```

**Step 3: Set environment variable**

```bash
vercel env add NEXT_PUBLIC_API_URL
# Enter: http://<YOUR_ORACLE_VM_IP>/api/v1
# Select: Production
```

**Step 4: Deploy**

```bash
vercel --prod
```

Save the deployment URL (e.g. `https://smart-tutor-xyz.vercel.app`).

**Step 5: Update CORS on backend**

Edit `.env` on the Oracle VM:

```bash
CORS_ORIGINS=["https://smart-tutor-xyz.vercel.app"]
```

Restart backend:

```bash
docker compose restart backend
```

---

### Task 16: Smoke test the live deployment

**Step 1: Test health endpoint**

```bash
curl http://<YOUR_ORACLE_VM_IP>/api/v1/health
```

Expected: `{"status": "healthy", ...}`

**Step 2: Test auth**

```bash
curl -X POST http://<YOUR_ORACLE_VM_IP>/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "litesh", "password": "Litesh@123"}'
```

Expected: JSON with `access_token`.

**Step 3: Test admin lockdown**

```bash
# Use token from step 2
curl http://<YOUR_ORACLE_VM_IP>/api/v1/admin/users \
  -H "Authorization: Bearer <TOKEN_FROM_STEP_2>"
```

Expected: 403 (non-admin user).

**Step 4: Open the Vercel frontend URL in browser**

Navigate to `https://smart-tutor-xyz.vercel.app`, log in, send a chat message, verify streaming works.

**Step 5: Commit deployment notes**

```bash
git add docs/
git commit -m "docs: record Oracle Cloud + Vercel deployment details"
```

---

## Success Criteria

- [ ] `pytest tests/` — 0 failures
- [ ] `npm test` — 0 failures
- [ ] `playwright test` — 0 failures on critical paths
- [ ] Admin endpoints return 403 for regular users
- [ ] Expired/blacklisted JWT returns 401
- [ ] Oracle VM: `docker compose ps` shows all services `Up`
- [ ] Vercel frontend loads and connects to Oracle backend
- [ ] Chat streaming works end-to-end on live URL
