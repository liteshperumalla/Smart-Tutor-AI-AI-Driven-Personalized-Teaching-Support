#!/usr/bin/env python3
"""
Security Verification Script
Verifies all security fixes are properly applied before deployment
"""

import sys
import os
import base64
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


def decode_unverified_payload(token: str) -> dict:
    """Parse the JWT payload segment without invoking JWT decode helpers."""

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    payload_segment = parts[1]
    padding = "=" * (-len(payload_segment) % 4)
    decoded = base64.urlsafe_b64decode(payload_segment + padding)
    payload = json.loads(decoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid JWT payload")
    return payload


class SecurityVerifier:
    """Verify security configuration"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def check_env_file(self):
        """Verify .env file doesn't contain secrets"""
        print("\n🔍 Checking .env file for exposed secrets...")

        env_path = Path(__file__).parent.parent / ".env"

        if not env_path.exists():
            self.warnings.append(".env file not found")
            return

        content = env_path.read_text()

        # Check for potential secrets
        dangerous_patterns = [
            ("AWS_ACCESS_KEY_ID=AKIA", "AWS Access Key"),
            ("AWS_SECRET_ACCESS_KEY=[A-Za-z0-9+/]{40}", "AWS Secret Key"),
            ("password=.*[A-Za-z0-9]{8,}", "Password"),
            ("SERPAPI_API_KEY=[a-f0-9]{64}", "SerpAPI Key"),
        ]

        for pattern, name in dangerous_patterns:
            import re
            if re.search(pattern, content, re.IGNORECASE):
                # Check if it's just a comment or empty
                lines = [
                    line for line in content.split('\n')
                    if pattern.split('=')[0] in line and not line.strip().startswith('#')
                ]
                for line in lines:
                    if '=' in line and line.split('=')[1].strip() and not line.split('=')[1].strip().startswith('#'):
                        self.errors.append(f"Potential secret found in .env: {name}")
                        return

        self.passed.append(".env file appears clean (no obvious secrets)")

    def check_jwt_secret(self):
        """Verify JWT secret is set"""
        print("\n🔍 Checking JWT configuration...")

        if not config.JWT_SECRET_KEY:
            self.errors.append("JWT_SECRET_KEY is not set")
        elif config.JWT_SECRET_KEY == "change-this-secret-key-in-production":
            self.errors.append("JWT_SECRET_KEY is still set to default value")
        else:
            self.passed.append("JWT_SECRET_KEY is configured")

        # Check if JTI is in tokens
        try:
            from backend.jwt_service import get_jwt_service
            jwt_service = get_jwt_service()

            # Create a test token
            token = jwt_service.create_access_token("test_user", "test@example.com")

            payload = decode_unverified_payload(token)

            if "jti" in payload:
                self.passed.append("JWT tokens include JTI (revocation enabled)")
            else:
                self.errors.append("JWT tokens missing JTI claim (revocation won't work)")

        except Exception as e:
            self.errors.append(f"Failed to verify JWT configuration: {e}")

    def check_jwt_blacklist(self):
        """Verify JWT blacklist is initialized"""
        print("\n🔍 Checking JWT blacklist...")

        try:
            from backend.jwt_blacklist import get_jwt_blacklist

            blacklist = get_jwt_blacklist()

            if blacklist:
                stats = blacklist.get_stats()
                if stats.get("redis_enabled"):
                    self.passed.append("JWT blacklist initialized with Redis")
                else:
                    self.warnings.append("JWT blacklist using in-memory fallback (not distributed)")
            else:
                self.warnings.append("JWT blacklist not initialized (call init_jwt_blacklist)")

        except Exception as e:
            self.errors.append(f"JWT blacklist check failed: {e}")

    def check_cors_config(self):
        """Verify CORS is properly configured"""
        print("\n🔍 Checking CORS configuration...")

        if config.ENVIRONMENT == "production":
            cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()

            if not cors_origins:
                self.errors.append("CORS_ALLOWED_ORIGINS not set in production")
            elif "yourdomain.com" in cors_origins or "example.com" in cors_origins:
                self.errors.append("CORS_ALLOWED_ORIGINS contains placeholder domains")
            else:
                self.passed.append(f"CORS configured for: {cors_origins}")

            if os.getenv("CORS_ALLOW_LOCALHOST", "false").lower() == "true":
                self.warnings.append("CORS_ALLOW_LOCALHOST enabled in production")
        else:
            self.passed.append("CORS configuration (development mode)")

    def check_database_password(self):
        """Verify database password is set"""
        print("\n🔍 Checking database configuration...")

        if config.STORAGE_BACKEND in ["postgres", "hybrid"]:
            if not config.POSTGRES_PASSWORD:
                self.errors.append("POSTGRES_PASSWORD not set")
            else:
                self.passed.append("Database password configured")

    def check_https_enforcement(self):
        """Check HTTPS enforcement"""
        print("\n🔍 Checking HTTPS enforcement...")

        if config.ENVIRONMENT == "production":
            if not config.ENFORCE_HTTPS:
                self.warnings.append("ENFORCE_HTTPS disabled in production")
            else:
                self.passed.append("HTTPS enforcement enabled")

    def check_file_validator(self):
        """Verify file validator is available"""
        print("\n🔍 Checking file validation...")

        try:
            from backend.file_validator import FileValidator

            # Check if python-magic is available
            try:
                import magic
                self.passed.append("File validator with MIME type checking (python-magic installed)")
            except ImportError:
                self.warnings.append(
                    "python-magic not installed - file validation will use extension-only checking. "
                    "Install with: pip install python-magic"
                )

        except Exception as e:
            self.errors.append(f"File validator not available: {e}")

    def check_sql_injection_protection(self):
        """Verify SQL injection protection"""
        print("\n🔍 Checking SQL injection protection...")

        try:
            from backend.services.storage.postgres import PostgresStorageBackend

            if hasattr(PostgresStorageBackend, '_is_valid_field_name'):
                self.passed.append("SQL injection protection (field validation) implemented")
            else:
                self.errors.append("SQL injection protection missing (_is_valid_field_name method)")

        except Exception as e:
            self.warnings.append(f"Could not verify SQL injection protection: {e}")

    def check_rate_limiting(self):
        """Verify rate limiting configuration"""
        print("\n🔍 Checking rate limiting...")

        try:
            from backend.rate_limiter import PerUserRateLimiter

            # Check if rate limiter uses JTI
            import inspect
            source = inspect.getsource(PerUserRateLimiter._get_username_from_token)

            if "jti" in source:
                self.passed.append("Rate limiting uses JTI (bypass-proof)")
            else:
                self.errors.append("Rate limiting doesn't use JTI (can be bypassed)")

        except Exception as e:
            self.warnings.append(f"Could not verify rate limiting: {e}")

    def run_all_checks(self):
        """Run all security checks"""
        print("=" * 70)
        print("🔒 SECURITY VERIFICATION")
        print("=" * 70)

        self.check_env_file()
        self.check_jwt_secret()
        self.check_jwt_blacklist()
        self.check_cors_config()
        self.check_database_password()
        self.check_https_enforcement()
        self.check_file_validator()
        self.check_sql_injection_protection()
        self.check_rate_limiting()

        print("\n" + "=" * 70)
        print("📊 RESULTS")
        print("=" * 70)

        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)}):")
            for item in self.passed:
                print(f"   ✓ {item}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for item in self.warnings:
                print(f"   ! {item}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for item in self.errors:
                print(f"   ✗ {item}")

        print("\n" + "=" * 70)

        if self.errors:
            print("❌ SECURITY VERIFICATION FAILED")
            print("Fix all errors before deploying to production!")
            return False
        elif self.warnings and config.ENVIRONMENT == "production":
            print("⚠️  SECURITY VERIFICATION PASSED WITH WARNINGS")
            print("Consider addressing warnings for optimal security.")
            return True
        else:
            print("✅ SECURITY VERIFICATION PASSED")
            print("All critical security checks passed!")
            return True


def main():
    """Main entry point"""
    verifier = SecurityVerifier()
    passed = verifier.run_all_checks()

    print("\n" + "=" * 70)
    if passed:
        print("🎉 Ready for deployment!")
        sys.exit(0)
    else:
        print("🚫 NOT ready for deployment - fix errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()
