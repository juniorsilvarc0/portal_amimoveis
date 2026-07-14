from datetime import datetime, timezone, timedelta
import bcrypt
from jose import jwt, JWTError

from app.config import settings


def create_access_token(data: dict) -> str:
    """Create a signed JWT access token with an expiry timestamp."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns the payload dict or None if invalid."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt. Truncates to 72 bytes (bcrypt limit)."""
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored hash.

    Supports two formats:
    - werkzeug legacy (scrypt:/pbkdf2:) — read-only fallback for pre-migration users.
    - bcrypt — current format.
    """
    if hashed.startswith(("scrypt:", "pbkdf2:")):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(hashed, plain)
        except Exception:
            return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False
