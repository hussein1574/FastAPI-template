import hashlib

from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from app.core.exceptions import UnauthorizedException
from app.schemas.token import TokenPayload
from app.core.config import get_settings
from jose import jwt, JWTError


pwd_context = CryptContext(schemes=['bcrypt'], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, settings.ALGORITHM)

def create_refresh_token(subject: Union[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.SECRET_KEY, settings.ALGORITHM)

def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, [settings.ALGORITHM])
        if(payload.get("type") != "access"):
            raise UnauthorizedException(detail="Invalid token type.")
        return TokenPayload(**payload)
    except JWTError:
        raise UnauthorizedException(detail="Could not validate credentials.")
    
def hash_token(token: str)-> str:
    return hashlib.sha256(token.encode()).hexdigest()