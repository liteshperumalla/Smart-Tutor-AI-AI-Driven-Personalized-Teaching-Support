from fastapi import FastAPI, Request, Response, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import ipaddress
import time

from backend.api.routes import register_routes
from backend.config import config
from backend.metrics import PrometheusMiddleware, metrics_handler, set_app_info
from backend.rate_limiter import limiter  # Import from rate_limiter to avoid circular imports

app = FastAPI(
    title="Smart AI Tutor API",
    version="1.0.0",
    docs_url="/docs" if config.ENVIRONMENT != "production" else None,  # Disable docs in production
    redoc_url="/redoc" if config.ENVIRONMENT != "production" else None
)

# Add rate limiting state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration - CRITICAL SECURITY FIX
# In production, this should be restricted to your actual frontend domain(s)
import os

# Get production domains from environment variable (comma-separated)
production_domains = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
production_domains = [d.strip() for d in production_domains if d.strip()]

if config.ENVIRONMENT == "production":
    # Production: Require explicit CORS configuration
    if not production_domains:
        # FAIL FAST: Do not start without CORS configuration
        raise RuntimeError(
            "CRITICAL: CORS_ALLOWED_ORIGINS must be set in production. "
            "Example: CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com"
        )

    allowed_origins = production_domains

    # Optionally allow localhost for testing (set CORS_ALLOW_LOCALHOST=true)
    # WARNING: This should be disabled in production
    if os.getenv("CORS_ALLOW_LOCALHOST", "false").lower() == "true":
        import logging
        logging.warning(
            "⚠️  SECURITY WARNING: CORS_ALLOW_LOCALHOST is enabled in production. "
            "This should be disabled for security."
        )
        allowed_origins.extend([
            "http://localhost:3000",
            "http://localhost:4000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:4000",
        ])
else:
    # Development: Allow localhost
    allowed_origins = [
        "http://localhost:3000",  # Next.js frontend
        "http://localhost:4000",  # Next.js frontend port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# HTTPS Enforcement Middleware
@app.middleware("http")
async def enforce_https(request: Request, call_next):
    """Enforce HTTPS in production and optionally in development"""
    if config.ENFORCE_HTTPS:
        # Check if request is over HTTP (not HTTPS)
        if request.url.scheme != "https":
            # Allow health check and docs on HTTP for internal use
            if request.url.path not in ["/health", "/docs", "/redoc", "/openapi.json"]:
                # Get the HTTPS URL
                https_url = request.url.replace(scheme="https")
                return JSONResponse(
                    status_code=307,  # Temporary Redirect
                    content={"detail": "HTTPS required"},
                    headers={"Location": str(https_url)}
                )

    response = await call_next(request)
    return response

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Content Security Policy - relaxed for API-only backend
    if config.ENVIRONMENT == "production":
        # API backend doesn't serve HTML, so CSP is minimal
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    return response

# Request timing middleware (for monitoring)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time header"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Add SlowAPI middleware for rate limiting
app.add_middleware(SlowAPIMiddleware)

# Add Prometheus metrics middleware
app.add_middleware(PrometheusMiddleware)

# Add security middleware
from backend.security_middleware import add_security_middleware
add_security_middleware(app, config={
    "max_request_size": config.MAX_UPLOAD_SIZE,
    "slow_request_threshold": 5.0,
    "max_auth_failures": 10,
    "block_duration": 900,  # 15 minutes
})

# Trusted Host middleware (prevent host header injection)
if config.ENVIRONMENT == "production":
    _trusted_hosts = os.environ.get("TRUSTED_HOSTS", "").split(",")
    _trusted_hosts = [h.strip() for h in _trusted_hosts if h.strip()]
    if _trusted_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=_trusted_hosts,
        )


@app.get("/")
async def root():
    return {"message": "Smart AI Tutor API", "version": "1.0.0"}


@app.get("/health")
@limiter.limit("10/minute")  # Rate limit health checks
async def health_check(request: Request):
    """Simple health check endpoint"""
    from backend.health import HealthChecker
    health = HealthChecker.get_simple_health()

    return {
        **health,
        "environment": config.ENVIRONMENT,
        "version": "1.0.0"
    }


@app.get("/health/detailed")
@limiter.limit("5/minute")  # More restrictive for detailed check
async def detailed_health_check(request: Request):
    """Detailed health check with all component status"""
    from backend.health import HealthChecker
    return HealthChecker.get_detailed_health()


@app.get("/csrf-token")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """
    Get CSRF token for the current session.

    This endpoint should be called on application load to obtain a CSRF token.
    The token will be set in a cookie and returned in the response.

    Returns:
        dict: Contains the CSRF token
    """
    from backend.csrf_protection import get_csrf_token

    token = get_csrf_token(request, response)
    return {
        "csrf_token": token,
        "header_name": "X-CSRF-Token",
        "message": "Include this token in X-CSRF-Token header for state-changing requests"
    }


@app.get("/metrics")
async def metrics(
    authorization: str | None = Header(None, alias="Authorization"),
    request: Request = None
):
    """
    Prometheus metrics endpoint with authentication.

    SECURITY: Requires valid authentication token.
    In production, consider restricting to admin role or IP whitelist.
    """
    from backend.auth_service import get_auth_service

    # SECURITY: Require authentication for metrics endpoint
    if not authorization:
        # Allow unauthenticated access only from explicitly trusted scrapers
        client_host = request.client.host if request else None
        # Only allow exact loopback addresses; Prometheus should use auth token
        # or be configured in METRICS_ALLOWED_IPS env var
        allowed_raw = os.environ.get("METRICS_ALLOWED_IPS", "127.0.0.1,::1,172.16.0.0/12").split(",")
        allowed_raw = [ip.strip() for ip in allowed_raw if ip.strip()]

        def _ip_allowed(host: str) -> bool:
            try:
                addr = ipaddress.ip_address(host)
            except ValueError:
                return False
            for entry in allowed_raw:
                try:
                    if "/" in entry:
                        if addr in ipaddress.ip_network(entry, strict=False):
                            return True
                    else:
                        if addr == ipaddress.ip_address(entry):
                            return True
                except ValueError:
                    continue
            return False

        if not client_host or not _ip_allowed(client_host):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for metrics endpoint"
            )
    else:
        # Validate token if provided
        try:
            token = authorization.split(" ")[1] if " " in authorization else authorization
            auth_service = get_auth_service()
            user = auth_service.validate_session(token)

            if user.get("role") != "Admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

    return metrics_handler()


# Startup event - validate configuration
@app.on_event("startup")
async def startup_event():
    """Validate configuration and initialize resources on startup"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Smart AI Tutor API Starting Up")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Storage Backend: {config.STORAGE_BACKEND}")
    logger.info(f"LLM Provider: {config.LLM_PROVIDER}")
    logger.info("=" * 60)

    # Validate configuration
    validation_result = config.validate()

    if validation_result["warnings"]:
        logger.warning("Configuration Warnings:")
        for warning in validation_result["warnings"]:
            logger.warning(f"  ⚠️  {warning}")

    if validation_result["errors"]:
        logger.error("Configuration Errors:")
        for error in validation_result["errors"]:
            logger.error(f"  ❌ {error}")

        # FAIL FAST: Do not start in production with configuration errors
        if config.ENVIRONMENT == "production":
            raise RuntimeError(
                "CRITICAL: Application cannot start in production with configuration errors. "
                "Fix the errors listed above and try again."
            )
        else:
            logger.error("⚠️  Application starting in development mode despite configuration errors")

    if validation_result["valid"]:
        logger.info("✅ Configuration validation passed")

    # Initialize Prometheus metrics metadata
    set_app_info(version="1.0.0", environment=config.ENVIRONMENT)
    logger.info("✅ Prometheus metrics initialized")

    # Initialize Langfuse tracing
    from backend.langfuse_setup import init_langfuse
    if init_langfuse():
        logger.info("✅ Langfuse tracing initialized")
    else:
        logger.info("ℹ️  Langfuse tracing not active")

    # Write reproducibility manifest (best-effort)
    if config.REPRODUCIBILITY_ENABLED:
        try:
            from backend.reproducibility import write_manifest
            write_manifest(config.REPRODUCIBILITY_MANIFEST_PATH)
            logger.info("✅ Reproducibility manifest written")
        except Exception as exc:
            logger.warning("Reproducibility manifest failed: %s", exc)

    # Cold-start warmup (best-effort)
    try:
        from backend.warmup import run_warmup
        await run_warmup()
    except Exception as exc:
        logger.warning("Warmup failed: %s", exc)

    # Seed admin user if none exists
    try:
        from backend.database import get_user_db
        import bcrypt

        user_db = get_user_db()
        users = user_db.list_users()
        has_admin = any(u.get("role") == "Admin" for u in users)

        if not has_admin:
            admin_password = os.environ.get("ADMIN_SEED_PASSWORD")
            if not admin_password:
                logger.warning("⚠️  No ADMIN_SEED_PASSWORD env var set — skipping admin seed")
            else:
                hashed = bcrypt.hashpw(
                    admin_password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")
                user_db.create_user(
                    username="admin",
                    password_hash=hashed,
                    email="admin@infra-mind.com",
                    full_name="Admin",
                    role="Admin",
                )
                logger.info("Admin user seeded (password from ADMIN_SEED_PASSWORD env var)")
        else:
            logger.info("✅ Admin user already exists")
    except Exception as e:
        logger.warning(f"⚠️  Admin seeding skipped: {e}")

    logger.info("=" * 60)


# Shutdown event - cleanup resources
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Smart AI Tutor API Shutting Down")
    logger.info("=" * 60)

    # Close database connections
    try:
        from backend.database import _user_db
        if _user_db and hasattr(_user_db, 'close'):
            _user_db.close()
            logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database connections: {e}")

    # Close Redis connections
    try:
        from backend.redis_cache import _redis_cache
        if _redis_cache and hasattr(_redis_cache, 'close'):
            _redis_cache.close()
            logger.info("✅ Redis connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis connections: {e}")

    # Flush Langfuse events
    try:
        from backend.langfuse_setup import shutdown_langfuse
        shutdown_langfuse()
        logger.info("✅ Langfuse events flushed")
    except Exception as e:
        logger.error(f"❌ Error flushing Langfuse: {e}")

    logger.info("=" * 60)
    logger.info("Shutdown complete")
    logger.info("=" * 60)


register_routes(app)
