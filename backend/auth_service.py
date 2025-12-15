"""
Authentication Service
Enhanced authentication with security features like rate limiting,
account lockout, and session management
"""

import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import secrets
import hashlib
import requests
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests

from .config import config
from .logger import get_logger
from .database import get_user_db
from .validators import PasswordValidator, UserLogin, UserRegistration
from .jwt_service import get_jwt_service
from .exceptions import (
    InvalidCredentialsError, UserAlreadyExistsError,
    AccountLockedError, PasswordValidationError,
    RateLimitError, SessionExpiredError
)

logger = get_logger(__name__)


class AuthService:
    """Authentication service with enhanced security"""

    def __init__(self):
        self.user_db = get_user_db()
        self.sessions: Dict[str, Dict[str, Any]] = {}  # Keep for backward compatibility during migration
        self._rate_limiter: Dict[str, list] = {}
        self.jwt_service = get_jwt_service()

    def _check_rate_limit(self, identifier: str) -> None:
        """
        Check rate limit for login attempts

        Args:
            identifier: User identifier (username or IP)

        Raises:
            RateLimitError: If rate limit exceeded
        """
        if not config.RATE_LIMIT_ENABLED:
            return

        now = datetime.now()
        cutoff = now - timedelta(seconds=config.RATE_LIMIT_PERIOD)

        # Initialize or clean old attempts
        if identifier not in self._rate_limiter:
            self._rate_limiter[identifier] = []

        self._rate_limiter[identifier] = [
            attempt for attempt in self._rate_limiter[identifier]
            if attempt > cutoff
        ]

        # Check limit
        if len(self._rate_limiter[identifier]) >= config.RATE_LIMIT_REQUESTS:
            retry_after = config.RATE_LIMIT_PERIOD
            logger.warning(f"Rate limit exceeded for: {identifier}")
            raise RateLimitError(retry_after)

        # Record attempt
        self._rate_limiter[identifier].append(now)

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def _check_account_locked(self, username: str) -> None:
        """
        Check if account is locked

        Args:
            username: Username to check

        Raises:
            AccountLockedError: If account is locked
        """
        if self.user_db.is_account_locked(username):
            user = self.user_db.get_user_safe(username)
            locked_until = user.get('locked_until', '')
            if locked_until:
                unlock_time = datetime.fromisoformat(locked_until)
                logger.warning(f"Login attempt on locked account: {username}")
                raise AccountLockedError(unlock_time.strftime("%Y-%m-%d %H:%M:%S"))

    def _handle_failed_login(self, username: str) -> None:
        """Handle failed login attempt"""
        if not self.user_db.user_exists(username):
            return

        attempts = self.user_db.increment_login_attempts(username)
        logger.warning(f"Failed login attempt #{attempts} for user: {username}")

        if attempts >= config.MAX_LOGIN_ATTEMPTS:
            # Lock account
            unlock_time = datetime.utcnow() + timedelta(seconds=config.LOCKOUT_DURATION)
            self.user_db.lock_account(username, unlock_time)
            logger.warning(f"Account locked due to failed attempts: {username}")

    def register_user(self, username: str, password: str,
                     confirm_password: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a new user

        Args:
            username: Desired username
            password: Password
            confirm_password: Password confirmation
            email: Optional email address

        Returns:
            User data (without password)

        Raises:
            UserAlreadyExistsError: If username exists
            PasswordValidationError: If password is weak
            ValidationError: If input is invalid
        """
        # Validate input
        user_data = UserRegistration(
            username=username,
            password=password,
            confirm_password=confirm_password,
            email=email
        )

        # Validate password strength
        PasswordValidator.validate_or_raise(password)

        # Check if user exists
        if self.user_db.user_exists(username):
            logger.warning(f"Registration attempt with existing username: {username}")
            raise UserAlreadyExistsError(username)

        # Hash password
        hashed_password = self._hash_password(password)

        # Create user
        user = self.user_db.create_user(
            username=username,
            hashed_password=hashed_password,
            email=email or ''
        )

        logger.info(f"User registered successfully: {username}")

        # Return user data without password
        safe_user = {k: v for k, v in user.items() if k != 'hashed_password'}
        safe_user['username'] = username
        return safe_user

    def login(self, username: str, password: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Authenticate user and create JWT tokens

        Args:
            username: Username
            password: Password

        Returns:
            Tuple of (tokens_dict, user_data)
            tokens_dict contains: access_token, refresh_token, token_type

        Raises:
            InvalidCredentialsError: If credentials are invalid
            AccountLockedError: If account is locked
            RateLimitError: If too many attempts
        """
        # Check rate limit
        self._check_rate_limit(username)

        # Validate input
        UserLogin(username=username, password=password)

        # Check if account is locked
        self._check_account_locked(username)

        # Get user
        user = self.user_db.get_user_safe(username)
        if not user:
            logger.warning(f"Login attempt with non-existent user: {username}")
            raise InvalidCredentialsError()

        # Verify password
        if not self._verify_password(password, user['hashed_password']):
            logger.warning(f"Invalid password for user: {username}")
            self._handle_failed_login(username)
            raise InvalidCredentialsError()

        # Reset failed login attempts on successful login
        self.user_db.reset_login_attempts(username)

        # Update last login
        self.user_db.update_last_login(username)

        # Create JWT tokens
        email = user.get('email', '')
        access_token = self.jwt_service.create_access_token(username=username, email=email)
        refresh_token = self.jwt_service.create_refresh_token(username=username, email=email)

        logger.info(f"User logged in successfully: {username}")

        # Return tokens and user data without password
        safe_user = {k: v for k, v in user.items() if k != 'hashed_password'}
        safe_user['username'] = username

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

        return tokens, safe_user

    def login_with_google(self, code: str, redirect_uri: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Google OAuth login - returns JWT tokens"""
        client_id = config.GOOGLE_OAUTH_CLIENT_ID
        client_secret = config.GOOGLE_OAUTH_CLIENT_SECRET
        if not client_id or not client_secret:
            raise InvalidCredentialsError("Google OAuth is not configured.")

        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        if token_response.status_code != 200:
            logger.error(f"Google token exchange failed: {token_response.text}")
            raise InvalidCredentialsError("Failed to verify Google credentials.")
        token_data = token_response.json()
        id_token_value = token_data.get("id_token")
        if not id_token_value:
            raise InvalidCredentialsError("Missing ID token from Google.")

        try:
            id_info = google_id_token.verify_oauth2_token(
                id_token_value,
                google_auth_requests.Request(),
                client_id,
            )
        except Exception as exc:
            logger.error(f"Failed to verify Google ID token: {exc}")
            raise InvalidCredentialsError("Invalid Google ID token.")

        email = id_info.get("email")
        username = email or f"google_{id_info.get('sub')}"
        if not username:
            raise InvalidCredentialsError("Unable to determine Google account identity.")

        if not self.user_db.user_exists(username):
            hashed_password = self._hash_password(secrets.token_urlsafe(16))
            self.user_db.create_user(
                username=username,
                hashed_password=hashed_password,
                email=email or "",
            )
            logger.info(f"Created new Google-linked user: {username}")

        self.user_db.update_last_login(username)

        # Create JWT tokens
        access_token = self.jwt_service.create_access_token(username=username, email=email or "")
        refresh_token = self.jwt_service.create_refresh_token(username=username, email=email or "")

        user = self.user_db.get_user(username)
        safe_user = {k: v for k, v in user.items() if k != 'hashed_password'}
        safe_user['username'] = username

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

        return tokens, safe_user

    def _create_session(self, username: str) -> str:
        """Create a new session"""
        session_token = secrets.token_urlsafe(32)
        self.sessions[session_token] = {
            'username': username,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=config.SESSION_TIMEOUT)
        }
        return session_token

    def validate_session(self, session_token: str) -> Dict[str, Any]:
        """
        Validate JWT token or legacy session token

        Args:
            session_token: JWT token or legacy session token

        Returns:
            User data

        Raises:
            SessionExpiredError: If session is invalid or expired
        """
        # First try JWT validation
        try:
            payload = self.jwt_service.verify_token(session_token, token_type="access")
            username = payload.get("sub")

            if not username:
                raise SessionExpiredError("Invalid token payload")

            # Get user data
            user = self.user_db.get_user(username)
            if not user:
                raise SessionExpiredError("User not found")

            safe_user = {k: v for k, v in user.items() if k != 'hashed_password'}
            safe_user['username'] = username
            safe_user['email'] = payload.get("email", "")
            return safe_user

        except SessionExpiredError:
            # If JWT validation fails, try legacy session (for backward compatibility)
            session = self.sessions.get(session_token)
            if not session:
                raise SessionExpiredError()

            # Check expiration
            if datetime.utcnow() > session['expires_at']:
                del self.sessions[session_token]
                raise SessionExpiredError()

            # Get user data
            username = session['username']
            user = self.user_db.get_user(username)

            safe_user = {k: v for k, v in user.items() if k != 'hashed_password'}
            safe_user['username'] = username
            return safe_user

    def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            New tokens dict with access_token and token_type

        Raises:
            SessionExpiredError: If refresh token is invalid
        """
        try:
            # Verify refresh token and get new access token
            new_access_token = self.jwt_service.refresh_access_token(refresh_token)

            logger.info("Access token refreshed successfully")

            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
            raise SessionExpiredError("Invalid refresh token")

    def logout(self, session_token: str) -> None:
        """Logout and invalidate session"""
        # For JWT tokens, we can't truly invalidate them without a token blacklist
        # For now, we just remove legacy sessions if they exist
        if session_token in self.sessions:
            username = self.sessions[session_token]['username']
            del self.sessions[session_token]
            logger.info(f"User logged out: {username}")
        else:
            # Try to extract username from JWT for logging
            try:
                payload = self.jwt_service.verify_token(session_token, token_type="access")
                username = payload.get("sub", "unknown")
                logger.info(f"User logged out: {username}")
            except:
                logger.info("User logged out (token already expired or invalid)")

    def change_password(self, username: str, old_password: str, new_password: str) -> None:
        """
        Change user password

        Args:
            username: Username
            old_password: Current password
            new_password: New password

        Raises:
            InvalidCredentialsError: If old password is wrong
            PasswordValidationError: If new password is weak
        """
        # Verify old password
        user = self.user_db.get_user(username)
        if not self._verify_password(old_password, user['hashed_password']):
            logger.warning(f"Failed password change attempt for: {username}")
            raise InvalidCredentialsError("Current password is incorrect")

        # Validate new password
        PasswordValidator.validate_or_raise(new_password)

        # Hash and update
        hashed_password = self._hash_password(new_password)
        self.user_db.update_user(username, {'hashed_password': hashed_password})

        logger.info(f"Password changed successfully for: {username}")

    def reset_password(self, username: str, new_password: str, reset_token: str) -> None:
        """
        Reset password using reset token

        Args:
            username: Username
            new_password: New password
            reset_token: Password reset token

        Note: Reset token validation should be implemented based on your requirements
        """
        # TODO: Implement token validation
        # For now, this is a placeholder

        # Validate new password
        PasswordValidator.validate_or_raise(new_password)

        # Hash and update
        hashed_password = self._hash_password(new_password)
        self.user_db.update_user(username, {
            'hashed_password': hashed_password,
            'login_attempts': 0,
            'locked_until': None
        })

        logger.info(f"Password reset for: {username}")

    def clean_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        now = datetime.utcnow()
        expired = [
            token for token, session in self.sessions.items()
            if session['expires_at'] < now
        ]

        for token in expired:
            del self.sessions[token]

        if expired:
            logger.info(f"Cleaned {len(expired)} expired sessions")

        return len(expired)


# Singleton instance
_auth_service = None


def get_auth_service() -> AuthService:
    """Get singleton auth service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
