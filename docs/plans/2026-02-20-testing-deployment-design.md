# Testing & Oracle Cloud Deployment Design
**Date:** 2026-02-20
**Approach:** Risk-First
**Goal:** Complete quality gate (bugs + security + coverage) before Oracle Cloud deploy

---

## Overview

Full testing pass across backend, frontend, and E2E before deploying the Smart AI Tutor to Oracle Cloud Always Free (ARM VM) with Vercel for the Next.js frontend.

---

## Testing Architecture

### Tools
- **Backend**: `pytest` + FastAPI `TestClient` (configured in `backend/pytest.ini`)
- **Frontend**: `Jest` + `React Testing Library`
- **E2E**: `Playwright` (configured in `e2e/playwright.config.ts`)
- **Security probes**: `pytest` + manual HTTP probes

### Test Pyramid
```
        [E2E - Playwright]          ← ~10 critical user journeys
      [Frontend - Jest/RTL]         ← ~15 component/hook tests
    [API Integration - pytest]      ← ~30 route tests
  [Unit - pytest]                   ← ~20 service/util tests
```

### Execution Order (Risk-First)
```
Phase 1 - Security     → Auth, JWT, CSRF, admin lockdown
Phase 2 - Core APIs    → Chat, RAG, file upload, quiz, profile, evaluation
Phase 3 - Frontend     → Components, API client, forms
Phase 4 - E2E          → Full user journeys in Playwright
Phase 5 - Deploy       → Oracle Cloud VM + Vercel
```

---

## Phase 1: Security & Authentication

### Files
- Expand: `backend/tests/test_auth.py`
- New: `backend/tests/test_security.py`

### Test Cases
| Test | Expected |
|------|----------|
| Expired JWT rejected | 401 |
| Blacklisted JWT after logout | 401 |
| Admin route `/admin/*` for non-admin | 403 |
| Missing CSRF token on mutating request | 403 |
| Rate limit exceeded | 429 |
| Weak password at signup | 400 |
| Duplicate username/email | 400 |
| Protected route without token | 401 (not 500) |
| SQL injection probe on login | 400/422 |
| Admin metrics without admin role | 403 |

---

## Phase 2: Core API Testing

### Chat (`backend/tests/test_chat.py` — expand)
- SSE stream returns chunks
- Session isolation (user A cannot access user B's sessions)
- Invalid session ID → 404
- Message history persists across requests

### Files (`backend/tests/test_files.py` — new)
- Valid PDF upload → 200
- Invalid file type → 400
- File exceeding size limit → 413

### Quiz (`backend/tests/test_quiz.py` — new)
- Create quiz, list quizzes, submit answers, retrieve results
- Auth required on all endpoints

### Profile (`backend/tests/test_profile.py` — new)
- Get profile, update profile
- Users cannot modify other users' profiles

### Evaluation (`backend/tests/test_evaluation.py` — new)
- Fetch evaluation data for completed assessment
- Auth required

---

## Phase 3: Frontend Testing

### Expand
- `frontend/src/lib/__tests__/api-client.test.ts` — error handling, 401 redirect, token refresh

### New
- `frontend/src/components/__tests__/auth-form.test.tsx` — login/signup form validation
- `frontend/src/components/__tests__/chat-interface.test.tsx` — message rendering, streaming state

---

## Phase 4: E2E Testing (Playwright)

### Expand
- `e2e/tests/auth.spec.ts` — login, logout, session persistence
- `e2e/tests/chat.spec.ts` — send message, receive stream, verify sources shown

### New
- `e2e/tests/quiz.spec.ts` — take quiz, view results
- `e2e/tests/profile.spec.ts` — update profile fields
- `e2e/tests/admin.spec.ts` — admin panel blocked for non-admin users

---

## Phase 5: Oracle Cloud Deployment

### Infrastructure
- **Compute**: Oracle Cloud Always Free ARM VM (4 OCPU, 24GB RAM)
- **Frontend**: Vercel free tier (Next.js)
- **Data**: DynamoDB + S3 remain on existing AWS account

### Steps
1. Provision Oracle Cloud ARM instance (Ubuntu 22.04)
2. Install Docker + Docker Compose v2
3. Copy repo + create production `.env`
4. Configure Nginx reverse proxy:
   - `/api/*` → FastAPI backend (port 8000)
   - `/` → Vercel frontend (or serve locally)
5. Obtain SSL certificate via Let's Encrypt (Certbot)
6. `docker compose up -d`
7. Deploy Next.js to Vercel with `NEXT_PUBLIC_API_URL` pointing to Oracle VM
8. Smoke test all critical paths on live URL

### Production `.env` Changes
- `JWT_SECRET` → strong random secret
- `POSTGRES_PASSWORD` → strong random password
- `REDIS_PASSWORD` → set password
- `CORS_ORIGINS` → restrict to Vercel domain
- `ENVIRONMENT=production`
- `DEBUG=false`

---

## Success Criteria

- [ ] All `pytest` tests pass with no failures
- [ ] No 500 errors on any tested endpoint
- [ ] Admin endpoints return 403 for non-admin JWT
- [ ] Expired/blacklisted JWT returns 401
- [ ] All Playwright E2E journeys complete without error
- [ ] Live Oracle + Vercel deployment passes smoke tests
