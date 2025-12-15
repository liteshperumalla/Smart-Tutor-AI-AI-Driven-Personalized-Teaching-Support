from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time

from backend.api.routes import register_routes
from backend.config import config

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

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
if config.ENVIRONMENT == "production":
    # Production: Restrict to specific origins
    allowed_origins = [
        "https://smartaitutor.yourdomain.com",  # Replace with your actual domain
        "https://app.yourdomain.com",
    ]
else:
    # Development: Allow localhost
    allowed_origins = [
        "http://localhost:3000",  # Next.js frontend
        "http://localhost:8501",  # Streamlit frontend
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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

    # Content Security Policy
    if config.ENVIRONMENT == "production":
        response.headers["Content-Security-Policy"] = "default-src 'self'"
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

# Trusted Host middleware (prevent host header injection)
if config.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["smartaitutor.yourdomain.com", "app.yourdomain.com"]  # Replace with your actual domains
    )


@app.get("/")
async def root():
    return {"message": "Smart AI Tutor API", "version": "1.0.0"}


@app.get("/health")
@limiter.limit("10/minute")  # Rate limit health checks
async def health_check(request: Request):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": config.ENVIRONMENT,
        "version": "1.0.0"
    }


register_routes(app)
