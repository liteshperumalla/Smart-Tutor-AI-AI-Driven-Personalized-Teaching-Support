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
from .jwt_blacklist import init_jwt_blacklist
from .exceptions import (
    InvalidCredentialsError, UserAlreadyExistsError,
    AccountLockedError, PasswordValidationError,
    RateLimitError, SessionExpiredError, TokenInvalidError,
    EmailNotVerifiedError, PasswordSetupRequiredError
)

logger = get_logger(__name__)


class AuthService:
    """Authentication service with enhanced security"""

    def __init__(self):
        self.user_db = get_user_db()
        self.sessions: Dict[str, Dict[str, Any]] = {}  # Keep for backward compatibility during migration
        self._rate_limiter: Dict[str, list] = {}
        self.jwt_service = get_jwt_service()

        # Initialize JWT blacklist with Redis if available
        try:
            if config.USE_REDIS_CACHE:
                from .redis_cache import RedisCache
                redis_cache = RedisCache()
                self.jwt_blacklist = init_jwt_blacklist(redis_cache=redis_cache)
                logger.info("JWT Blacklist initialized with Redis support")
            else:
                self.jwt_blacklist = init_jwt_blacklist(redis_cache=None)
                logger.warning("JWT Blacklist initialized without Redis (in-memory fallback)")
        except Exception as e:
            logger.error(f"Failed to initialize JWT Blacklist: {e}")
            self.jwt_blacklist = init_jwt_blacklist(redis_cache=None)
            logger.warning("JWT Blacklist initialized with in-memory fallback")

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

    @staticmethod
    def _hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_metadata(user: Dict[str, Any]) -> Dict[str, Any]:
        metadata = user.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return metadata

    @staticmethod
    def _generate_verification_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

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
                     confirm_password: str, email: Optional[str] = None,
                     full_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a new user

        Args:
            username: Desired username
            password: Password
            confirm_password: Password confirmation
            email: Optional email address
            full_name: Optional full name

        Returns:
            User data (without password)

        Raises:
            UserAlreadyExistsError: If username exists
            PasswordValidationError: If password is weak
            ValidationError: If input is invalid
        """
        if not email:
            raise InvalidCredentialsError("Email is required for signup verification")

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
            password_hash=hashed_password,
            email=email or '',
            full_name=full_name or username
        )

        metadata = self._normalize_metadata(user)
        metadata["email_verified"] = False
        metadata["password_set"] = True
        self.user_db.update_user(username, {"metadata": metadata})

        try:
            self.request_email_verification(username=username)
        except Exception as e:
            logger.warning(f"Email verification send failed during registration (non-fatal): {e}")

        logger.info(f"User registered successfully: {username}")

        # Return user data without password
        safe_user = {k: v for k, v in user.items() if k not in ['password_hash', 'hashed_password']}
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

        # Get user - try by username first, then by email
        user = self.user_db.get_user_safe(username)
        actual_username = username

        if not user:
            # Try to find user by email
            user = self.user_db.get_user_by_email(username)
            if user:
                actual_username = user.get("username", username)

        if not user:
            logger.warning(f"Login attempt with non-existent user: {username}")
            raise InvalidCredentialsError()

        # Check if account is locked
        self._check_account_locked(actual_username)

        # Verify password
        password_hash = user.get("password_hash") or user.get("hashed_password")
        if not password_hash or not self._verify_password(password, password_hash):
            logger.warning(f"Invalid password for user: {actual_username}")
            self._handle_failed_login(actual_username)
            raise InvalidCredentialsError()

        metadata = self._normalize_metadata(user)
        if metadata.get("email_verified") is False:
            logger.warning(f"Login blocked - email not verified: {actual_username}")
            raise EmailNotVerifiedError("Email not verified. Check your inbox for the code.")

        # Reset failed login attempts on successful login
        self.user_db.reset_login_attempts(actual_username)

        # Update last login
        self.user_db.update_last_login(actual_username)

        # Create JWT tokens
        email = user.get('email', '')
        access_token = self.jwt_service.create_access_token(username=actual_username, email=email)
        refresh_token = self.jwt_service.create_refresh_token(username=actual_username, email=email)

        logger.info(f"User logged in successfully: {actual_username}")

        # Return tokens and user data without password
        safe_user = {k: v for k, v in user.items() if k not in ['hashed_password', 'password_hash']}
        safe_user['username'] = actual_username

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

        return tokens, safe_user

    def request_email_verification(
        self, username: Optional[str] = None, email: Optional[str] = None
    ) -> None:
        user = self._resolve_user_for_reset(username=username, email=email)
        if not user:
            return

        user_email = user.get("email") or ""
        if not user_email:
            logger.warning("Email verification requested but no email is set for user")
            return

        metadata = self._normalize_metadata(user)
        if metadata.get("email_verified") is True:
            return

        code = self._generate_verification_code()
        code_hash = self._hash_value(code)
        expires_at = (datetime.utcnow() + timedelta(
            seconds=config.EMAIL_VERIFICATION_CODE_TTL_SECONDS
        )).isoformat()

        metadata["email_verification"] = {
            "code_hash": code_hash,
            "expires_at": expires_at,
            "issued_at": datetime.utcnow().isoformat(),
        }
        metadata["email_verified"] = False
        self.user_db.update_user(user["username"], {"metadata": metadata})

        self._send_email_verification_code(
            to_email=user_email,
            username=user["username"],
            code=code,
        )

    def confirm_email_verification(self, username: str, code: str) -> None:
        user = self.user_db.get_user_safe(username)
        if not user:
            raise TokenInvalidError("Invalid verification request")

        metadata = self._normalize_metadata(user)
        verification = metadata.get("email_verification") if isinstance(metadata, dict) else None
        if not verification:
            raise TokenInvalidError("Verification code not found")

        code_hash = verification.get("code_hash")
        expires_at = verification.get("expires_at")
        if not code_hash or not expires_at:
            raise TokenInvalidError("Invalid verification code")

        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except Exception:
            raise TokenInvalidError("Invalid verification code")

        if datetime.utcnow() > expires_dt:
            raise TokenInvalidError("Verification code expired")

        if not secrets.compare_digest(self._hash_value(code), code_hash):
            raise TokenInvalidError("Invalid verification code")

        metadata["email_verified"] = True
        metadata.pop("email_verification", None)
        self.user_db.update_user(username, {"metadata": metadata})

    def _send_email_verification_code(
        self, to_email: str, username: str, code: str
    ) -> None:
        if not config.SMTP_SERVER or not config.SMTP_USERNAME or not config.SMTP_PASSWORD:
            raise RuntimeError("SMTP is not configured")

        from_email = config.EMAIL_FROM or config.SMTP_USERNAME
        expires_minutes = int(config.EMAIL_VERIFICATION_CODE_TTL_SECONDS / 60)

        subject = "Smart AI Tutor Email Verification Code"
        body = (
            f"Hello {username},\n\n"
            "Use the verification code below to confirm your Smart AI Tutor account:\n"
            f"{code}\n\n"
            f"This code expires in {expires_minutes} minutes.\n\n"
            "If you did not create this account, you can ignore this email."
        )
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background: #ffffff; color: #000000; padding: 24px;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #000000; padding: 24px;">
              <h2 style="margin: 0 0 12px;">Verify your Smart AI Tutor account</h2>
              <p style="margin: 0 0 16px;">Hi {username},</p>
              <p style="margin: 0 0 16px;">
                Use the code below to verify your email. It expires in {expires_minutes} minutes.
              </p>
              <p style="margin: 0 0 24px; font-size: 24px; font-weight: 700; letter-spacing: 0.2em;">
                {code}
              </p>
              <p style="margin: 0; font-size: 12px; color: #000000;">
                If you did not create this account, you can ignore this email.
              </p>
            </div>
          </body>
        </html>
        """

        from email.message import EmailMessage
        import smtplib

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(body)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)

    def login_with_google(self, code: str, redirect_uri: str) -> Tuple[Optional[Dict[str, str]], Dict[str, Any], Optional[str]]:
        """Google OAuth login - returns JWT tokens or a password setup token"""
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

        if not id_info.get("email_verified"):
            raise InvalidCredentialsError("Google account email is not verified.")

        email = id_info.get("email")
        username = email or f"google_{id_info.get('sub')}"
        if not username:
            raise InvalidCredentialsError("Unable to determine Google account identity.")

        if not self.user_db.user_exists(username):
            hashed_password = self._hash_password(secrets.token_urlsafe(16))
            user = self.user_db.create_user(
                username=username,
                password_hash=hashed_password,
                email=email or "",
                full_name=id_info.get("name") or username,
            )
            metadata = self._normalize_metadata(user)
            metadata["email_verified"] = True
            metadata["password_set"] = False
            metadata["auth_provider"] = "google"
            self.user_db.update_user(username, {"metadata": metadata})
            logger.info(f"Created new Google-linked user: {username}")
        else:
            existing = self.user_db.get_user(username)
            metadata = self._normalize_metadata(existing)
            if metadata.get("email_verified") is not True:
                metadata["email_verified"] = True
                metadata["auth_provider"] = metadata.get("auth_provider") or "google"
                self.user_db.update_user(username, {"metadata": metadata})

        self.user_db.update_last_login(username)

        user = self.user_db.get_user(username)
        metadata = self._normalize_metadata(user)
        password_set = metadata.get("password_set")
        if password_set is False:
            setup_token = self.create_password_setup_token(username)
            safe_user = {k: v for k, v in user.items() if k not in ['hashed_password', 'password_hash']}
            safe_user['username'] = username
            return None, safe_user, setup_token

        # Create JWT tokens
        access_token = self.jwt_service.create_access_token(username=username, email=email or "")
        refresh_token = self.jwt_service.create_refresh_token(username=username, email=email or "")

        safe_user = {k: v for k, v in user.items() if k not in ['hashed_password', 'password_hash']}
        safe_user['username'] = username

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

        return tokens, safe_user, None

    def create_password_setup_token(self, username: str) -> str:
        user = self.user_db.get_user_safe(username)
        if not user:
            raise InvalidCredentialsError("User not found")

        token = secrets.token_urlsafe(32)
        token_hash = self._hash_value(token)
        expires_at = (datetime.utcnow() + timedelta(
            seconds=config.PASSWORD_SETUP_TOKEN_TTL_SECONDS
        )).isoformat()

        metadata = self._normalize_metadata(user)
        metadata["password_setup"] = {
            "token_hash": token_hash,
            "expires_at": expires_at,
        }
        metadata["password_set"] = False
        self.user_db.update_user(username, {"metadata": metadata})
        return token

    def _find_user_by_password_setup_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Fallback lookup when provided username does not match the active setup token."""
        provided_hash = self._hash_value(token)
        now = datetime.utcnow()

        for user in self.user_db.list_users():
            metadata = self._normalize_metadata(user)
            token_info = metadata.get("password_setup") if isinstance(metadata, dict) else None
            if not token_info:
                continue

            token_hash = token_info.get("token_hash")
            expires_at = token_info.get("expires_at")
            if not token_hash or not expires_at:
                continue

            try:
                expires_dt = datetime.fromisoformat(expires_at)
            except Exception:
                continue
            if now > expires_dt:
                continue

            if secrets.compare_digest(provided_hash, token_hash):
                username = user.get("username")
                if not username:
                    continue
                full_user = self.user_db.get_user_safe(username)
                if full_user:
                    return full_user
        return None

    def complete_password_setup(
        self, username: str, token: str, new_password: str, confirm_password: str
    ) -> Dict[str, Any]:
        token = (token or "").strip()
        if new_password != confirm_password:
            raise InvalidCredentialsError("Passwords do not match")

        user = self.user_db.get_user_safe(username)
        if not user:
            user = self._find_user_by_password_setup_token(token)
        if not user:
            raise TokenInvalidError("Invalid password setup token")

        metadata = self._normalize_metadata(user)
        token_info = metadata.get("password_setup") if isinstance(metadata, dict) else None
        if not token_info:
            raise TokenInvalidError("Invalid password setup token")

        token_hash = token_info.get("token_hash")
        expires_at = token_info.get("expires_at")
        if not token_hash or not expires_at:
            raise TokenInvalidError("Invalid password setup token")

        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except Exception:
            raise TokenInvalidError("Invalid password setup token")

        if datetime.utcnow() > expires_dt:
            raise TokenInvalidError("Password setup token has expired")

        provided_hash = self._hash_value(token)
        if not secrets.compare_digest(provided_hash, token_hash):
            raise TokenInvalidError("Invalid password setup token")

        PasswordValidator.validate_or_raise(new_password)

        # Always persist using the resolved account username from the token lookup.
        # The submitted identifier may be stale/alternate (e.g. email vs username).
        resolved_username = user.get("username") or username

        hashed_password = self._hash_password(new_password)
        metadata.pop("password_setup", None)
        metadata["password_set"] = True
        metadata.setdefault("email_verified", True)
        self.user_db.update_user(resolved_username, {
            "password_hash": hashed_password,
            "login_attempts": 0,
            "locked_until": None,
            "metadata": metadata,
        })

        safe_user = {k: v for k, v in user.items() if k not in ['hashed_password', 'password_hash']}
        safe_user['username'] = resolved_username
        return safe_user

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
            # Check if token is blacklisted (logged out)
            if self.jwt_blacklist and self.jwt_blacklist.is_blacklisted(session_token):
                logger.warning("Attempt to use blacklisted (logged out) token")
                raise SessionExpiredError("Token has been revoked")

            payload = self.jwt_service.verify_token(session_token, token_type="access")
            username = payload.get("sub")

            if not username:
                raise SessionExpiredError("Invalid token payload")

            # Get user data
            user = self.user_db.get_user(username)
            if not user:
                raise SessionExpiredError("User not found")

            safe_user = {k: v for k, v in user.items() if k not in ['hashed_password', 'password_hash']}
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

            safe_user = {k: v for k, v in user.items() if k not in ['hashed_password', 'password_hash']}
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
        """
        Logout and invalidate session.
        Adds JWT token to blacklist to prevent further use.
        """
        # Remove legacy sessions if they exist
        if session_token in self.sessions:
            username = self.sessions[session_token]['username']
            del self.sessions[session_token]
            logger.info(f"User logged out (legacy session): {username}")
            return

        # For JWT tokens, add to blacklist
        try:
            # Verify the token first to get its expiration
            payload = self.jwt_service.verify_token(session_token, token_type="access")
            username = payload.get("sub", "unknown")

            # Calculate remaining time until token expiration
            exp = payload.get("exp")
            if exp:
                expiry_seconds = max(int(exp - datetime.now().timestamp()), 0)
            else:
                # Default to access token expiry if not found
                expiry_seconds = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

            # Add to blacklist
            if self.jwt_blacklist:
                self.jwt_blacklist.blacklist_token(session_token, expiry_seconds)
                logger.info(f"User logged out and token blacklisted: {username}")
            else:
                logger.warning(f"JWT blacklist not available, token not revoked for: {username}")

        except SessionExpiredError:
            # Token already expired, no need to blacklist
            logger.info("User logged out (token already expired)")
        except Exception as e:
            # Log error but don't fail the logout
            logger.error(f"Error during logout: {e}")
            logger.info("User logged out (token may not be blacklisted)")

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
        password_hash = user.get("password_hash") or user.get("hashed_password")
        if not password_hash or not self._verify_password(old_password, password_hash):
            logger.warning(f"Failed password change attempt for: {username}")
            raise InvalidCredentialsError("Current password is incorrect")

        # Validate new password
        PasswordValidator.validate_or_raise(new_password)

        # Hash and update
        hashed_password = self._hash_password(new_password)
        self.user_db.update_user(username, {'password_hash': hashed_password})

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
        # Validate reset token
        user = self.user_db.get_user_safe(username)
        if not user:
            raise TokenInvalidError("Invalid password reset token")

        metadata = user.get("metadata") or {}
        token_info = metadata.get("password_reset") if isinstance(metadata, dict) else None
        if not token_info:
            raise TokenInvalidError("Invalid password reset token")

        token_hash = token_info.get("token_hash")
        expires_at = token_info.get("expires_at")
        if not token_hash or not expires_at:
            raise TokenInvalidError("Invalid password reset token")

        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except Exception:
            raise TokenInvalidError("Invalid password reset token")

        if datetime.utcnow() > expires_dt:
            raise TokenInvalidError("Password reset token has expired")

        provided_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(provided_hash, token_hash):
            raise TokenInvalidError("Invalid password reset token")

        # Validate new password
        PasswordValidator.validate_or_raise(new_password)

        # Hash and update
        hashed_password = self._hash_password(new_password)
        if isinstance(metadata, dict):
            metadata.pop("password_reset", None)

        self.user_db.update_user(username, {
            'password_hash': hashed_password,
            'login_attempts': 0,
            'locked_until': None,
            'metadata': metadata if isinstance(metadata, dict) else {},
        })

        logger.info(f"Password reset for: {username}")

    def create_password_reset_token(self, username: str) -> str:
        """Generate and store a password reset token."""
        user = self.user_db.get_user_safe(username)
        if not user:
            raise InvalidCredentialsError("User not found")

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = (datetime.utcnow() + timedelta(seconds=config.PASSWORD_RESET_TOKEN_TTL_SECONDS)).isoformat()

        metadata = user.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["password_reset"] = {
            "token_hash": token_hash,
            "expires_at": expires_at,
        }

        self.user_db.update_user(username, {"metadata": metadata})
        return token

    def request_password_reset(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        redirect_url: Optional[str] = None,
    ) -> None:
        """Generate a reset token and send it via email (if possible)."""
        user = self._resolve_user_for_reset(username=username, email=email)
        if not user:
            return

        user_email = user.get("email") or ""
        if not user_email:
            logger.warning("Password reset requested but no email is set for user")
            return

        token = self.create_password_reset_token(user["username"])
        self._send_password_reset_email(
            to_email=user_email,
            username=user["username"],
            token=token,
            redirect_url=redirect_url,
        )

    def _resolve_user_for_reset(
        self, username: Optional[str], email: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if username:
            user = self.user_db.get_user_safe(username)
            if user:
                user["username"] = username
                if email and user.get("email") and user.get("email") != email:
                    return None
                return user
            return None

        if email:
            user = None
            lookup = getattr(self.user_db, "get_user_by_email", None)
            if callable(lookup):
                user = lookup(email)
            if user and "username" in user:
                return user
        return None

    def _send_password_reset_email(
        self,
        to_email: str,
        username: str,
        token: str,
        redirect_url: Optional[str],
    ) -> None:
        if not config.SMTP_SERVER or not config.SMTP_USERNAME or not config.SMTP_PASSWORD:
            raise RuntimeError("SMTP is not configured")

        from_email = config.EMAIL_FROM or config.SMTP_USERNAME
        expires_minutes = int(config.PASSWORD_RESET_TOKEN_TTL_SECONDS / 60)
        reset_link = ""
        if redirect_url:
            from urllib.parse import urlparse
            parsed_url = urlparse(redirect_url)
            if parsed_url.scheme in ["http", "https"] and parsed_url.netloc in config.ALLOWED_REDIRECT_DOMAINS:
                separator = "&" if "?" in redirect_url else "?"
                reset_link = f"{redirect_url}{separator}token={token}&username={username}"
            else:
                logger.warning(f"Invalid redirect_url provided for password reset: {redirect_url}")

        subject = "Smart AI Tutor Password Reset"
        if reset_link:
            body = (
                f"Hello {username},\n\n"
                "We received a request to reset your Smart AI Tutor password.\n"
                f"Reset your password using this link (expires in {expires_minutes} minutes):\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can ignore this email."
            )
            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background: #ffffff; color: #000000; padding: 24px;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #000000; padding: 24px;">
                  <h2 style="margin: 0 0 12px;">Reset your Smart AI Tutor password</h2>
                  <p style="margin: 0 0 16px;">Hi {username},</p>
                  <p style="margin: 0 0 16px;">
                    We received a request to reset your password. This link expires in {expires_minutes} minutes.
                  </p>
                  <p style="margin: 0 0 24px;">
                    <a href="{reset_link}" style="background: #000000; color: #ffffff; padding: 12px 18px; text-decoration: none;">
                      Reset password
                    </a>
                  </p>
                  <p style="margin: 0 0 8px; font-size: 12px; color: #000000;">
                    If the button does not work, copy and paste this link:
                  </p>
                  <p style="margin: 0 0 16px; font-size: 12px; color: #000000; word-break: break-all;">
                    {reset_link}
                  </p>
                  <p style="margin: 0; font-size: 12px; color: #000000;">
                    If you did not request this, you can ignore this email.
                  </p>
                </div>
              </body>
            </html>
            """
        else:
            body = (
                f"Hello {username},\n\n"
                "We received a request to reset your Smart AI Tutor password.\n"
                f"Use the token below (expires in {expires_minutes} minutes):\n"
                f"{token}\n\n"
                "If you didn't request this, you can ignore this email."
            )
            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background: #ffffff; color: #000000; padding: 24px;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #000000; padding: 24px;">
                  <h2 style="margin: 0 0 12px;">Reset your Smart AI Tutor password</h2>
                  <p style="margin: 0 0 16px;">Hi {username},</p>
                  <p style="margin: 0 0 16px;">
                    Use the token below within {expires_minutes} minutes:
                  </p>
                  <p style="margin: 0 0 24px; font-size: 20px; font-weight: 600; letter-spacing: 0.04em;">
                    {token}
                  </p>
                  <p style="margin: 0; font-size: 12px; color: #000000;">
                    If you did not request this, you can ignore this email.
                  </p>
                </div>
              </body>
            </html>
            """

        from email.message import EmailMessage
        import smtplib

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(body)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)

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
