import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    # Bcrypt requires max 72 bytes
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email, role=role)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

# ==========================================
# RFC 6238 Standard TOTP & 2FA Implementation
# ==========================================
import os
import hmac
import hashlib
import time
import base64
import struct
import secrets

def generate_totp_secret() -> str:
    """Generates a standard 160-bit (20 byte) base32 TOTP secret key."""
    return base64.b32encode(os.urandom(20)).decode("utf-8").replace("=", "")

def get_totp_token(secret: str, interval: Optional[int] = None) -> str:
    """Calculates the 6-digit TOTP code for a given base32 secret and 30-second interval."""
    if interval is None:
        interval = int(time.time()) // 30
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    msg = struct.pack(">Q", interval)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[19] & 15
    token = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{token:06d}"

def verify_totp_token(secret: str, token: str, valid_window: int = 1) -> bool:
    """Verifies a 6-digit TOTP token allowing +/- valid_window clock drift."""
    token = token.strip()
    if len(token) != 6 or not token.isdigit():
        return False
    current_interval = int(time.time()) // 30
    for offset in range(-valid_window, valid_window + 1):
        if get_totp_token(secret, current_interval + offset) == token:
            return True
    return False

def generate_backup_codes(count: int = 5) -> list[str]:
    """Generates a list of single-use 8-digit alphanumeric backup codes."""
    return [secrets.token_hex(4).upper() for _ in range(count)]
