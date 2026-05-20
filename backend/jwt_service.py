"""
JWT Service
Handles JWT token generation, validation, and refresh
Supports both HS256 (symmetric) and RS256 (asymmetric) algorithms
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
from jwt.exceptions import PyJWTError as JWTError
from pathlib import Path
import uuid
import base64
import json
from .config import config
from .logger import get_logger
from .exceptions import SessionExpiredError

logger = get_logger(__name__)


class JWTService:
    """JWT token management service"""

    def __init__(self):
        self.algorithm = config.JWT_ALGORITHM
        self.access_token_expire_minutes = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        self.issuer = config.JWT_ISSUER
        self.audience = config.JWT_AUDIENCE

        # Load appropriate keys based on algorithm
        if self.algorithm == "RS256":
            # Load RSA keys for asymmetric signing
            self._load_rsa_keys()
            logger.info("JWT Service initialized with RS256 (asymmetric)")
        else:
            # Use secret key for symmetric signing (HS256)
            self.secret_key = config.JWT_SECRET_KEY
            self.private_key = None
            self.public_key = None
            logger.info(f"JWT Service initialized with {self.algorithm} (symmetric)")

    def _load_rsa_keys(self):
        """Load RSA private and public keys from PEM files"""
        try:
            # Get key paths
            private_key_path = Path(config.JWT_PRIVATE_KEY_PATH)
            public_key_path = Path(config.JWT_PUBLIC_KEY_PATH)

            # Load private key
            if private_key_path.exists():
                with open(private_key_path, 'r') as f:
                    self.private_key = f.read()
                logger.info(f"Loaded RSA private key from {private_key_path}")
            else:
                raise FileNotFoundError(f"RSA private key not found: {private_key_path}")

            # Load public key
            if public_key_path.exists():
                with open(public_key_path, 'r') as f:
                    self.public_key = f.read()
                logger.info(f"Loaded RSA public key from {public_key_path}")
            else:
                raise FileNotFoundError(f"RSA public key not found: {public_key_path}")

            self.secret_key = None  # Not used with RS256

        except Exception as e:
            logger.error(f"Failed to load RSA keys: {e}")
            if getattr(config, "ENVIRONMENT", "").lower() == "production":
                # Refusing to silently downgrade to symmetric signing in production —
                # JWT_SECRET_KEY may be weak/default and forge-able. Fail loud.
                raise RuntimeError(
                    "RS256 keys are required in production but could not be loaded. "
                    "Refusing to fall back to HS256."
                ) from e
            logger.warning("Falling back to HS256 with secret key (non-production only)")
            self.algorithm = "HS256"
            self.secret_key = config.JWT_SECRET_KEY
            self.private_key = None
            self.public_key = None

    def _get_signing_key(self):
        """Get the appropriate signing key based on algorithm"""
        if self.algorithm == "RS256":
            return self.private_key
        else:
            return self.secret_key

    def _get_verification_key(self):
        """Get the appropriate verification key based on algorithm"""
        if self.algorithm == "RS256":
            return self.public_key
        else:
            return self.secret_key

    def create_access_token(
        self,
        username: str,
        email: str = "",
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create JWT access token

        Args:
            username: User's username
            email: User's email address
            additional_claims: Additional claims to include in token

        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)

        claims = {
            "sub": username,  # Subject (user identifier)
            "email": email,
            "exp": expire,  # Expiration time
            "iat": now,  # Issued at
            "iss": self.issuer,  # Issuer
            "aud": self.audience,  # Audience
            "type": "access",  # Token type
            "jti": str(uuid.uuid4())  # JWT ID - unique identifier for token revocation
        }

        # Add additional claims if provided
        if additional_claims:
            claims.update(additional_claims)

        signing_key = self._get_signing_key()
        token = jwt.encode(claims, signing_key, algorithm=self.algorithm)
        logger.debug(f"Created access token for user: {username} using {self.algorithm}")
        return token

    def create_refresh_token(
        self,
        username: str,
        email: str = ""
    ) -> str:
        """
        Create JWT refresh token

        Args:
            username: User's username
            email: User's email address

        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)

        claims = {
            "sub": username,
            "email": email,
            "exp": expire,
            "iat": now,
            "iss": self.issuer,
            "aud": self.audience,
            "jti": str(uuid.uuid4()),  # JWT ID - unique identifier for token revocation
            "type": "refresh"  # Token type
        }

        signing_key = self._get_signing_key()
        token = jwt.encode(claims, signing_key, algorithm=self.algorithm)
        logger.debug(f"Created refresh token for user: {username} using {self.algorithm}")
        return token

    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify and decode JWT token

        Args:
            token: JWT token to verify
            token_type: Expected token type ('access' or 'refresh')

        Returns:
            Decoded token payload

        Raises:
            SessionExpiredError: If token is invalid or expired
        """
        try:
            # Decode and verify token
            verification_key = self._get_verification_key()
            payload = jwt.decode(
                token,
                verification_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience
            )

            # Check token type
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type. Expected: {token_type}, Got: {payload.get('type')}")
                raise SessionExpiredError("Invalid token type")

            return payload

        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise SessionExpiredError("Invalid or expired token")

    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Create new access token from refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token

        Raises:
            SessionExpiredError: If refresh token is invalid
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, token_type="refresh")

        # Extract user info
        username = payload.get("sub")
        email = payload.get("email", "")

        if not username:
            raise SessionExpiredError("Invalid refresh token payload")

        # Create new access token
        return self.create_access_token(username=username, email=email)

    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        Get token expiration time

        Args:
            token: JWT token

        Returns:
            Expiration datetime or None if invalid
        """
        try:
            payload = _decode_unverified_payload(token)
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp, tz=timezone.utc)
        except (JWTError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.debug(f"Failed to decode token expiry: {exc}")
        return None

    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired

        Args:
            token: JWT token

        Returns:
            True if expired, False otherwise
        """
        expiry = self.get_token_expiry(token)
        if not expiry:
            return True
        return datetime.now(timezone.utc) > expiry


# Singleton instance
import threading as _threading
_jwt_service = None
_jwt_service_lock = _threading.Lock()


def _decode_unverified_payload(token: str) -> Dict[str, Any]:
    """Parse the JWT payload segment without trusting it for authentication."""

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


def get_jwt_service() -> JWTService:
    """Get singleton JWT service instance (double-checked locking)."""
    global _jwt_service
    if _jwt_service is None:
        with _jwt_service_lock:
            if _jwt_service is None:
                _jwt_service = JWTService()
    return _jwt_service
