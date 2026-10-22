"""
Authentication Utilities
JWT token generation, password hashing, email verification
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets
import os
from dotenv import load_dotenv

load_dotenv()

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-min-32-characters-long")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
RESET_TOKEN_EXPIRE_HOURS = 24  # 24 hours
VERIFICATION_TOKEN_EXPIRE_HOURS = 48  # 48 hours

# HTTP Bearer security scheme
security = HTTPBearer()


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    # Convert password to bytes and hash it
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in token (usually user_id and email)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded token data or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_reset_token() -> str:
    """
    Generate a secure random token for password reset.
    
    Returns:
        Random URL-safe token
    """
    return secrets.token_urlsafe(32)


def generate_verification_token() -> str:
    """
    Generate a secure random token for email verification.
    
    Returns:
        Random URL-safe token
    """
    return secrets.token_urlsafe(32)


def get_password_reset_expiry() -> datetime:
    """
    Get expiry datetime for password reset token.
    
    Returns:
        Datetime object (24 hours from now)
    """
    return datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)


def get_verification_expiry() -> datetime:
    """
    Get expiry datetime for email verification token.
    
    Returns:
        Datetime object (48 hours from now)
    """
    return datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_EXPIRE_HOURS)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets minimum security requirements.
    
    Args:
        password: Password to validate
        
    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    # Check for special characters
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"
    
    return True, "Password is strong"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current authenticated user from JWT token.
    
    This is a dependency function that extracts and validates the JWT token
    from the Authorization header and returns the corresponding user.
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        
    Returns:
        User object from database
        
    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    # Import here to avoid circular dependency
    from app.core.database import SessionLocal
    from app.models.user import User
    
    # Create database session
    db = SessionLocal()
    
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        return user
    finally:
        db.close()
