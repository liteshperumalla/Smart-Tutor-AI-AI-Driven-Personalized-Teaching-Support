# HttpOnly Cookies Migration Guide

**Security Enhancement:** JWT tokens moved from localStorage to secure HttpOnly cookies

**Date:** 2025-12-28
**Severity:** HIGH (XSS Protection)
**Status:** ✅ IMPLEMENTED

---

## Overview

This application has been upgraded to use **HttpOnly cookies** for authentication tokens instead of localStorage. This is a critical security improvement that prevents XSS (Cross-Site Scripting) attacks from stealing user authentication tokens.

### Security Benefits

| Feature | localStorage (OLD) | HttpOnly Cookies (NEW) |
|---------|-------------------|------------------------|
| **XSS Protection** | ❌ Vulnerable | ✅ Protected |
| **JavaScript Access** | ✅ Readable | ❌ Cannot read (secure) |
| **Automatic Transmission** | ❌ Manual | ✅ Automatic |
| **CSRF Protection** | ❌ None | ✅ SameSite=Lax |
| **Secure Flag** | ❌ N/A | ✅ HTTPS only (prod) |

---

## What Changed

### Backend Changes

#### 1. Authentication Endpoints (✅ Completed)

**File:** `backend/api/routes/auth.py`

**Login Endpoint (`/auth/login`):**
- **Before:** Returned tokens in response body
  ```json
  {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "user": {...}
  }
  ```

- **After:** Sets tokens in HttpOnly cookies
  ```python
  response.set_cookie(
      key="access_token",
      value=access_token,
      httponly=True,    # XSS protection
      secure=True,      # HTTPS only (production)
      samesite="lax",   # CSRF protection
      max_age=900       # 15 minutes
  )
  ```
  Returns only user info:
  ```json
  {
    "user": {...},
    "message": "Login successful. Tokens set in secure cookies."
  }
  ```

**Google OAuth Callback (`/auth/google/callback`):**
- Same changes as login endpoint
- Sets access_token and refresh_token in cookies
- Returns user info only

**Token Refresh (`/auth/refresh`):**
- **Before:** Required refresh token in request body
- **After:** Reads refresh token from HttpOnly cookie
- Sets new access token in cookie automatically

**Logout (`/auth/logout`):**
- Added cookie clearing:
  ```python
  response.delete_cookie(key="access_token", path="/")
  response.delete_cookie(key="refresh_token", path="/")
  ```

#### 2. Authentication Dependencies (✅ Completed)

**File:** `backend/api/dependencies.py`

**Token Resolution Priority:**
1. **HttpOnly cookie** (most secure, primary method)
2. **Authorization header** (backward compatibility only)
3. ~~**Query string**~~ (REMOVED for security)

```python
def _resolve_token(request: Request, authorization: str | None) -> str:
    # 1. Try HttpOnly cookie first (NEW)
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token.strip()

    # 2. Fall back to Authorization header (backward compatibility)
    if authorization:
        return authorization.split(" ", 1)[1].strip()

    # 3. Query string tokens are NO LONGER SUPPORTED
    raise HTTPException(status_code=401, detail="Missing authentication")
```

**Security Removed:**
- ❌ Query string authentication (`?token=...`) - **REMOVED** (prevents log exposure)

### Frontend Changes

#### 1. Auth Library (✅ Completed)

**File:** `frontend/src/lib/auth.ts`

**Complete Rewrite for HttpOnly Cookies:**

```typescript
// OLD (INSECURE):
export function saveAuthToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);  // ❌ Vulnerable to XSS
  setCookie(TOKEN_KEY, token);              // ❌ Not HttpOnly
}

// NEW (SECURE):
export function saveAuthToken(_token: string) {
  // Backend sets HttpOnly cookies automatically
  // Frontend cannot and should not store tokens
  window.dispatchEvent(
    new CustomEvent(AUTH_STATE_CHANGED_EVENT, { detail: "authenticated" })
  );
}
```

**Key Changes:**
- `saveAuthToken()` - Now a no-op (tokens managed by backend)
- `getAuthToken()` - Always returns `null` (cannot read HttpOnly cookies)
- `clearAuthToken()` - Dispatches event only (backend clears cookies)
- `checkAuthStatus()` - NEW function to check authentication via API call

#### 2. API Client (✅ Completed)

**File:** `frontend/src/lib/api.ts`

**All fetch calls now include `credentials: "include"`:**

```typescript
async function request<T>(path: string, init?: RequestInit) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",  // ✅ Send HttpOnly cookies automatically
  });
}
```

**This applies to ALL API functions:**
- ✅ `postJSON()`
- ✅ `getJSON()`
- ✅ `patchJSON()`
- ✅ `deleteJSON()`
- ✅ `uploadResearchFile()`
- ✅ `fetchWithAuth()`
- ✅ All 50+ API endpoint functions

---

## Cookie Configuration

### Development Environment

```typescript
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,      // Cannot be accessed by JavaScript
    secure=False,       // HTTP allowed in development
    samesite="lax",     // CSRF protection, allows OAuth redirects
    max_age=900,        // 15 minutes
    path="/",
)
```

### Production Environment

```typescript
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,      // Cannot be accessed by JavaScript
    secure=True,        // ✅ HTTPS REQUIRED
    samesite="lax",     // CSRF protection
    max_age=900,        // 15 minutes
    path="/",
)
```

### Cookie Attributes Explained

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httponly` | `True` | **XSS Protection** - JavaScript cannot access cookie |
| `secure` | `True` (prod) | **HTTPS Only** - Cookie only sent over encrypted connection |
| `samesite` | `"lax"` | **CSRF Protection** - Prevents cross-site request attacks while allowing OAuth |
| `max_age` | `900` (15 min) | **Token Lifetime** - Access token expires after 15 minutes |
| `path` | `"/"` | **Scope** - Cookie sent for all paths on domain |

---

## Migration Guide for Developers

### Step 1: Update Backend Dependencies

```bash
cd backend
# No new dependencies needed - uses built-in FastAPI Response
```

### Step 2: Rebuild Docker Containers

```bash
# Rebuild with updated security changes
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Step 3: Test Authentication Flow

#### Login Test
```bash
# Test login with cookie inspection
curl -v -X POST http://localhost:8010/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "password"}' \
  --cookie-jar cookies.txt

# Should see in response headers:
# Set-Cookie: access_token=eyJ...; HttpOnly; Path=/; Max-Age=900; SameSite=Lax
# Set-Cookie: refresh_token=eyJ...; HttpOnly; Path=/; Max-Age=604800; SameSite=Lax
```

#### Authenticated Request Test
```bash
# Test authenticated request with cookies
curl -v http://localhost:8010/auth/me \
  --cookie cookies.txt

# Should return user info without Authorization header
```

#### Logout Test
```bash
# Test logout (clears cookies)
curl -v -X POST http://localhost:8010/auth/logout \
  --cookie cookies.txt

# Should see in response headers:
# Set-Cookie: access_token=; Path=/; Max-Age=0
# Set-Cookie: refresh_token=; Path=/; Max-Age=0
```

### Step 4: Frontend Testing

#### Browser DevTools Check

1. **Open DevTools → Application → Cookies**
2. After login, verify cookies exist:
   - `access_token` - HttpOnly ✓, Secure (in prod) ✓, SameSite=Lax ✓
   - `refresh_token` - HttpOnly ✓, Secure (in prod) ✓, SameSite=Lax ✓

3. **Open DevTools → Console**
4. Try to access cookies (should fail):
   ```javascript
   document.cookie  // Should NOT show access_token or refresh_token
   ```

#### React Component Testing

```typescript
// In any component
import { checkAuthStatus } from "@/lib/auth";

// Check if user is authenticated
const isAuthenticated = await checkAuthStatus(getApiBaseUrl());
console.log("Authenticated:", isAuthenticated);
```

---

## Breaking Changes

### Frontend Code Updates Required

#### ❌ **STOP doing this:**
```typescript
// OLD CODE - DO NOT USE
const token = getAuthToken();
if (token) {
  // Make authenticated request
  fetch("/api/data", {
    headers: {
      "Authorization": `Bearer ${token}`  // ❌ Old method
    }
  });
}
```

#### ✅ **START doing this:**
```typescript
// NEW CODE - CORRECT METHOD
// Just make the request - cookies are sent automatically
fetch("/api/data", {
  credentials: "include"  // ✅ Sends HttpOnly cookies
});

// Or use the API client (already includes credentials)
import { getJSON } from "@/lib/api";
const data = await getJSON({ path: "/data" });  // ✅ Automatic
```

### Common Migration Issues

#### Issue 1: "No authentication token" error

**Cause:** Frontend not sending cookies
**Fix:** Ensure `credentials: "include"` in fetch calls

```typescript
// Add to all fetch calls
fetch(url, {
  credentials: "include",  // Required!
  ...otherOptions
});
```

#### Issue 2: Cookies not persisting

**Cause:** SameSite attribute blocking cookies
**Fix:** Verify frontend and backend are on same domain/port in development

```bash
# Development setup:
Backend:  http://localhost:8010
Frontend: http://localhost:4000

# Both use localhost - cookies will work
```

#### Issue 3: CORS errors

**Cause:** CORS not configured for credentials
**Fix:** Backend CORS configuration (already implemented):

```python
# backend/api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,  # ✅ Required for cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## Backward Compatibility

### During Migration Period

The implementation supports **both** authentication methods during migration:

1. **HttpOnly Cookies** (primary, recommended)
2. **Authorization Header** (fallback, deprecated)

This allows gradual migration of clients without breaking existing integrations.

### How It Works

```python
# Backend checks cookies first, then Authorization header
def _resolve_token(request: Request, authorization: str | None) -> str:
    # 1. Check cookie (new method)
    if request.cookies.get("access_token"):
        return request.cookies.get("access_token")

    # 2. Check Authorization header (old method - backward compat)
    if authorization:
        return authorization.split(" ", 1)[1]

    # 3. Neither found - unauthorized
    raise HTTPException(status_code=401)
```

### Deprecation Timeline

- **Phase 1 (Current):** Both methods supported
- **Phase 2 (Future):** Authorization header deprecated, warnings added
- **Phase 3 (TBD):** Authorization header removed, cookies only

---

## Security Testing

### XSS Attack Simulation

**Test that tokens cannot be stolen via XSS:**

1. Open browser console on authenticated page
2. Try to steal tokens:
   ```javascript
   // This should NOT reveal access_token or refresh_token
   console.log(document.cookie);

   // Try localStorage (should be empty)
   console.log(localStorage.getItem('satAuthToken'));  // null
   ```

3. Inject malicious script (test environment only):
   ```javascript
   // Simulate XSS attack trying to steal tokens
   const stolenTokens = {
     cookie: document.cookie,  // Should NOT contain tokens
     localStorage: localStorage.getItem('satAuthToken')  // Should be null
   };

   // Send to "attacker server" (should get nothing)
   console.log("Stolen data:", stolenTokens);
   ```

4. **Expected Result:** Attacker gets NO tokens (HttpOnly protection working)

### CSRF Attack Simulation

**Test that CSRF protection works:**

1. Create malicious page on different domain:
   ```html
   <!-- evil-site.com -->
   <form action="http://localhost:8010/profile/password" method="POST">
     <input name="new_password" value="hacked123">
   </form>
   <script>document.forms[0].submit();</script>
   ```

2. **Expected Result:** Request BLOCKED by SameSite=Lax

### Manual Security Checks

```bash
# 1. Verify HttpOnly flag
curl -v http://localhost:8010/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' \
  2>&1 | grep -i "set-cookie"

# Should see: HttpOnly

# 2. Verify Secure flag (production only)
# In production, should see: Secure

# 3. Verify SameSite
# Should see: SameSite=Lax

# 4. Verify Max-Age
# access_token: Max-Age=900 (15 minutes)
# refresh_token: Max-Age=604800 (7 days)
```

---

## Troubleshooting

### Problem: "Invalid or expired session" on every request

**Diagnosis:**
```bash
# Check if cookies are being set
curl -v http://localhost:8010/auth/login ... | grep Set-Cookie

# Check if cookies are being sent
curl -v http://localhost:8010/auth/me --cookie "access_token=..."
```

**Solutions:**
1. Verify `credentials: "include"` in fetch calls
2. Check CORS `allow_credentials=True` in backend
3. Ensure same domain/port for frontend and backend in development

### Problem: Cookies not visible in DevTools

**Cause:** HttpOnly cookies don't appear in document.cookie
**Solution:** Check DevTools → Application → Cookies (not Console)

### Problem: Logout doesn't clear cookies

**Diagnosis:**
```bash
# Check logout response
curl -v -X POST http://localhost:8010/auth/logout --cookie cookies.txt
```

**Solution:** Verify `clear_auth_cookies()` is called in logout endpoint

### Problem: Token refresh not working

**Cause:** Refresh token not found in cookie
**Fix:**
1. Verify refresh token cookie exists (check DevTools)
2. Ensure cookie max_age is not expired
3. Check that refresh endpoint reads from `request.cookies.get("refresh_token")`

---

## Performance Considerations

### Cookie Size

- **access_token:** ~200-300 bytes (JWT with user claims)
- **refresh_token:** ~200-300 bytes
- **Total:** ~500 bytes per request

**Impact:** Negligible - cookies sent in every request header

### Comparison

| Method | Storage | Request Overhead | Security |
|--------|---------|------------------|----------|
| localStorage + Header | Client | ~100 bytes | ❌ Vulnerable |
| HttpOnly Cookies | Client | ~500 bytes | ✅ Secure |

**Verdict:** Security benefit >> 400 byte overhead

---

## Compliance & Best Practices

### OWASP Recommendations

✅ **A02:2021 – Cryptographic Failures**
- Tokens not stored in localStorage (XSS protection)
- HTTPS enforced in production (Secure flag)

✅ **A07:2021 – Identification and Authentication Failures**
- Short session timeouts (15 minutes)
- Automatic token refresh
- Secure cookie attributes

### Industry Standards

✅ **NIST SP 800-63B** (Digital Identity Guidelines)
- Tokens have limited lifetime
- Secure storage (HttpOnly cookies)
- Transport security (HTTPS)

✅ **PCI DSS** (if handling payments)
- Authentication credentials protected
- Secure transmission (HTTPS)
- Session timeout implemented

---

## Next Steps

### Recommended Enhancements

1. **Implement CSRF Tokens** (MEDIUM priority)
   - Add CSRF token validation for state-changing operations
   - Set CSRF token in regular cookie, verify in requests

2. **Add Token Fingerprinting** (LOW priority)
   - Bind tokens to user agent + IP
   - Detect token theft/reuse

3. **Implement Token Rotation** (MEDIUM priority)
   - Rotate refresh tokens on use
   - Invalidate old refresh tokens

4. **Add Session Management** (LOW priority)
   - List active sessions
   - Remote logout capability

---

## Summary

### What We Achieved

✅ **Eliminated XSS token theft** - HttpOnly cookies cannot be accessed by JavaScript
✅ **Added CSRF protection** - SameSite=Lax prevents cross-site attacks
✅ **Enforced HTTPS** - Secure flag ensures encrypted transmission (production)
✅ **Removed insecure methods** - Query string authentication eliminated
✅ **Backward compatibility** - Authorization header still supported during migration

### Security Posture

**Before:**
- Risk Level: HIGH (XSS vulnerable)
- Attack Surface: Large (tokens in localStorage)

**After:**
- Risk Level: MODERATE (XSS protected)
- Attack Surface: Minimal (tokens in HttpOnly cookies)

### Production Checklist

Before deploying to production:

- [ ] Verify `ENVIRONMENT=production` in `.env`
- [ ] Confirm `Secure` flag is set (HTTPS only)
- [ ] Test login/logout flow
- [ ] Verify cookies are HttpOnly in browser
- [ ] Test authentication on all protected endpoints
- [ ] Monitor for authentication errors in logs
- [ ] Have rollback plan ready

---

**Implementation Date:** 2025-12-28
**Implemented By:** Claude Sonnet 4.5
**Review Status:** Pending security team review
**Next Review:** After production deployment

---

## References

- [OWASP HttpOnly Cookie Guide](https://owasp.org/www-community/HttpOnly)
- [MDN: Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [RFC 6265: HTTP State Management Mechanism](https://tools.ietf.org/html/rfc6265)
- [FastAPI Response Cookies](https://fastapi.tiangolo.com/advanced/response-cookies/)
