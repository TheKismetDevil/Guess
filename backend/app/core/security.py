from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password hashes starting with this prefix can never be used to log in
# (placeholder accounts created for historical QQ identities use it).
UNUSABLE_PASSWORD_PREFIX = "!"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(UNUSABLE_PASSWORD_PREFIX):
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def opaque_key(kind: str, value: str) -> str:
    """Stable public identifier that does not reveal the underlying value (e.g. a QQ number)."""
    digest = hmac.new(settings.jwt_secret.encode(), f'{kind}:{value}'.encode(), hashlib.sha256).hexdigest()
    return f'{kind}:{digest}'


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=settings.refresh_token_expire_days))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
