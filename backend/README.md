# Backend Services

This directory contains the backend services layer for Smart AI Tutor, providing robust, secure, and scalable backend functionality.

## 📁 Structure

```
backend/
├── __init__.py           # Package initialization
├── config.py             # Configuration management
├── exceptions.py         # Custom exception hierarchy
├── logger.py             # Structured logging system
├── validators.py         # Input validation & security
├── database.py           # Database service layer
├── auth_service.py       # Authentication service
├── cache.py              # Caching layer
├── utils.py              # Common utilities
└── README.md             # This file
```

## 🚀 Features

### 1. Configuration Management (`config.py`)
- Centralized configuration from environment variables
- Validation of required settings
- Support for multiple environments (dev, staging, production)
- Secure secrets management

### 2. Custom Exceptions (`exceptions.py`)
- Structured exception hierarchy
- Error codes and messages
- Detailed error context
- Easy error handling and debugging

### 3. Structured Logging (`logger.py`)
- JSON and text log formats
- Contextual logging (user_id, session_id, etc.)
- Log rotation and management
- Multiple log levels

### 4. Input Validation (`validators.py`)
- Pydantic models for data validation
- Password strength validation
- Path sanitization (prevents path traversal)
- File upload validation
- XSS prevention
- Rate limiting

### 5. Database Layer (`database.py`)
- Thread-safe JSON database
- Transaction support
- User management
- Chat session management
- Proper error handling

### 6. Authentication Service (`auth_service.py`)
- Secure password hashing (bcrypt)
- Session management
- Account lockout after failed attempts
- Rate limiting
- Password validation
- OAuth integration ready

### 7. Caching Layer (`cache.py`)
- LRU cache with TTL
- Thread-safe operations
- Cache statistics
- Decorator for easy caching
- Multiple named caches

### 8. Utilities (`utils.py`)
- File operations
- Date/time utilities
- String manipulation
- Token generation
- Retry logic
- Health checks

## 📖 Usage Examples

### Configuration

```python
from backend.config import config

# Access configuration
model_name = config.EMBEDDING_MODEL
debug_mode = config.DEBUG

# Validate configuration
validation = config.validate()
if not validation['valid']:
    print("Configuration errors:", validation['errors'])
```

### Logging

```python
from backend.logger import get_logger

logger = get_logger(__name__)

# Basic logging
logger.info("User logged in")
logger.error("Database connection failed", exc_info=True)

# Contextual logging
logger.set_context(user_id="user123", session_id="sess456")
logger.info("Query processed")  # Automatically includes context
```

### Validation

```python
from backend.validators import UserRegistration, PasswordValidator

# Validate user registration
try:
    user_data = UserRegistration(
        username="johndoe",
        password="SecurePass123!",
        confirm_password="SecurePass123!",
        email="john@example.com"
    )
except ValidationError as e:
    print(f"Validation failed: {e}")

# Validate password strength
is_valid, violations = PasswordValidator.validate_password("weak")
if not is_valid:
    print("Password violations:", violations)
```

### Database Operations

```python
from backend.database import get_user_db

user_db = get_user_db()

# Create user
user = user_db.create_user(
    username="johndoe",
    hashed_password="hashed_password_here",
    email="john@example.com"
)

# Get user
user = user_db.get_user("johndoe")

# Update user
user_db.update_user("johndoe", {
    "display_name": "John Doe",
    "theme": "dark"
})
```

### Authentication

```python
from backend.auth_service import get_auth_service

auth = get_auth_service()

# Register user
try:
    user = auth.register_user(
        username="johndoe",
        password="SecurePass123!",
        confirm_password="SecurePass123!",
        email="john@example.com"
    )
except UserAlreadyExistsError:
    print("User already exists")

# Login
try:
    session_token, user_data = auth.login("johndoe", "SecurePass123!")
    print(f"Session token: {session_token}")
except InvalidCredentialsError:
    print("Invalid credentials")
except AccountLockedError as e:
    print(f"Account locked: {e.message}")
```

### Caching

```python
from backend.cache import cached, get_cache_manager

# Use decorator
@cached(cache_name="api_responses", ttl=300)
def expensive_operation(param1, param2):
    # Expensive computation
    return result

# Manual caching
cache_manager = get_cache_manager()
user_cache = cache_manager.get_cache("users")

# Set value
user_cache.set("user_123", user_data, ttl=600)

# Get value
user_data = user_cache.get("user_123")

# Get stats
stats = user_cache.get_stats()
print(f"Cache hit rate: {stats['hit_rate']}")
```

### Exception Handling

```python
from backend.exceptions import UserNotFoundError, ValidationError

try:
    user = user_db.get_user("unknown_user")
except UserNotFoundError as e:
    print(f"Error: {e.message}")
    print(f"Error code: {e.code}")
    error_dict = e.to_dict()  # For JSON APIs
```

## 🔐 Security Features

1. **Password Security**
   - Bcrypt hashing with salt
   - Configurable password requirements
   - Common password detection

2. **Rate Limiting**
   - Prevents brute force attacks
   - Configurable limits per user/IP

3. **Account Lockout**
   - Automatic lockout after failed attempts
   - Configurable lockout duration

4. **Input Validation**
   - Path traversal prevention
   - XSS prevention
   - SQL injection prevention (for future SQL DB)
   - File upload validation

5. **Session Management**
   - Secure session tokens
   - Configurable session timeout
   - Session cleanup

## 🔧 Configuration

Copy `.env.example` to `.env` and update with your values:

```bash
cp .env.example .env
```

### Required Configuration

- `SECRET_KEY`: Secret key for cryptographic operations
- `USERS_FILE`: Path to users database file
- `LLM_MODEL`: LLM model to use
- `EMBEDDING_MODEL`: Embedding model to use

### Optional Configuration

- `LANGFUSE_*`: Langfuse monitoring keys
- `GOOGLE_OAUTH_*`: Google OAuth credentials
- `SMTP_*`: Email server settings
- `SERPAPI_API_KEY`: Web search API key

## 🧪 Testing

```python
# Test configuration
from backend.config import validate_config

result = validate_config()
print("Configuration valid:", result['valid'])
print("Warnings:", result['warnings'])
print("Errors:", result['errors'])

# Test cache
from backend.cache import get_cache_manager

cache_manager = get_cache_manager()
cache_manager.get_all_stats()
cache_manager.cleanup_all_expired()

# Test database
from backend.database import get_user_db

user_db = get_user_db()
print("Users:", len(user_db.list_users()))
```

## 📝 Migration Guide

To migrate existing code to use the new backend:

### Before:
```python
import json
users = json.load(open('users.json'))
user = users.get(username)
```

### After:
```python
from backend.database import get_user_db
user_db = get_user_db()
user = user_db.get_user(username)
```

## 🚨 Error Handling Best Practices

```python
from backend.exceptions import SmartTutorException
from backend.logger import get_logger

logger = get_logger(__name__)

try:
    # Your code
    pass
except SmartTutorException as e:
    # Handle application-specific errors
    logger.error(f"Application error: {e.message}", extra=e.details)
    # Return user-friendly error
    return {"error": e.code, "message": e.message}
except Exception as e:
    # Handle unexpected errors
    logger.exception("Unexpected error occurred")
    return {"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
```

## 📊 Monitoring

```python
from backend.cache import get_cache_manager
from backend.logger import get_logger

# Cache statistics
cache_manager = get_cache_manager()
stats = cache_manager.get_all_stats()
logger.info("Cache stats", extra=stats)

# Health checks
from backend.utils import HealthCheck

disk_info = HealthCheck.check_disk_space()
if not disk_info['healthy']:
    logger.warning("Low disk space", extra=disk_info)
```

## 🔄 Future Enhancements

- [ ] SQL database support (PostgreSQL, MySQL)
- [ ] Redis caching support
- [ ] Celery for background tasks
- [ ] JWT token authentication
- [ ] API rate limiting middleware
- [ ] Metrics collection (Prometheus)
- [ ] Database migrations (Alembic)
- [ ] OpenTelemetry integration

## 📚 Additional Resources

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Bcrypt Documentation](https://github.com/pyca/bcrypt/)
- [Python Logging](https://docs.python.org/3/library/logging.html)

## 🤝 Contributing

When adding new backend features:

1. Follow the existing code structure
2. Add proper error handling
3. Include logging
4. Add type hints
5. Update this README
6. Add examples

## 📄 License

Part of Smart AI Tutor project.
