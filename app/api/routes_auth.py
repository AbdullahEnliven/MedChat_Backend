"""
Authentication Routes
User signup, login, logout, password reset, email verification
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date
import os
import uuid
from pathlib import Path

from app.core.database import get_db
from app.models.user import User, PasswordReset, EmailVerification
from app.utils.auth import (
    hash_password, 
    verify_password, 
    create_access_token,
    decode_access_token,
    generate_reset_token,
    generate_verification_token,
    get_password_reset_expiry,
    get_verification_expiry,
    validate_password_strength,
    get_current_user
)
from app.utils.email_service import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# Pydantic Models
class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    gender: Optional[str] = None  # 'male', 'female', 'other', 'prefer_not_to_say'
    date_of_birth: Optional[date] = None  # Birthday in YYYY-MM-DD format
    
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v):
        if v is not None:
            allowed_values = ['male', 'female', 'other', 'prefer_not_to_say']
            if v.lower() not in allowed_values:
                raise ValueError(f'Gender must be one of: {", ".join(allowed_values)}')
            return v.lower()
        return v
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_date_of_birth(cls, v):
        if v is not None:
            # Check if date is not in the future
            if v > date.today():
                raise ValueError('Date of birth cannot be in the future')
            
            # Check if age is reasonable (0-150 years)
            age = (date.today() - v).days // 365
            if age > 150:
                raise ValueError('Invalid date of birth')
                
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_verified: bool
    created_at: datetime
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    profile_photo_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# Dependency to get current verified user
async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure current user has verified their email."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address to access this feature"
        )
    return current_user


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Creates new user, sends verification email.
    """
    try:
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered. Please use a different email or login."
            )
        
        # Validate password strength
        is_valid, message = validate_password_strength(request.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Calculate age if date_of_birth is provided
        age = None
        if request.date_of_birth:
            today = date.today()
            age = today.year - request.date_of_birth.year - (
                (today.month, today.day) < (request.date_of_birth.month, request.date_of_birth.day)
            )
        
        # Create new user
        hashed_pwd = hash_password(request.password)
        new_user = User(
            email=request.email,
            full_name=request.full_name,
            hashed_password=hashed_pwd,
            gender=request.gender,
            date_of_birth=request.date_of_birth,
            age=age,
            is_verified=False,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Generate verification token
        verification_token = generate_verification_token()
        verification = EmailVerification(
            user_id=new_user.id,
            token=verification_token,
            expires_at=get_verification_expiry()
        )
        db.add(verification)
        db.commit()
        
        # Send verification email (optional - catch exceptions to not fail signup)
        try:
            send_verification_email(new_user.email, new_user.full_name, verification_token)
        except Exception as email_error:
            print(f"Warning: Could not send verification email: {str(email_error)}")
            # Continue with signup even if email fails
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Signup error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create account: {str(e)}"
        )
    
    # Create access token
    access_token = create_access_token(
        data={"user_id": new_user.id, "email": new_user.email}
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(new_user)
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Returns JWT access token on success.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact support."
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email}
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@router.post("/verify-email")
async def verify_email(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """
    Verify user email with verification token.
    """
    # Find verification token
    verification = db.query(EmailVerification).filter(
        EmailVerification.token == request.token
    ).first()
    
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    # Check if already verified
    if verification.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Check if expired
    if verification.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token expired. Please request a new one."
        )
    
    # Mark as verified
    verification.is_verified = True
    verification.verified_at = datetime.utcnow()
    
    # Update user
    user = db.query(User).filter(User.id == verification.user_id).first()
    user.is_verified = True
    
    db.commit()
    
    # Send welcome email
    send_welcome_email(user.email, user.full_name)
    
    return {
        "message": "Email verified successfully!",
        "user_id": user.id,
        "email": user.email
    }


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request password reset email.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    # Don't reveal if email exists or not (security best practice)
    if not user:
        return {
            "message": "If an account exists with this email, you will receive a password reset link."
        }
    
    # Generate reset token
    reset_token = generate_reset_token()
    password_reset = PasswordReset(
        user_id=user.id,
        token=reset_token,
        expires_at=get_password_reset_expiry()
    )
    db.add(password_reset)
    db.commit()
    
    # Send reset email
    send_password_reset_email(user.email, user.full_name, reset_token)
    
    return {
        "message": "If an account exists with this email, you will receive a password reset link."
    }


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using reset token.
    """
    # Find reset token
    password_reset = db.query(PasswordReset).filter(
        PasswordReset.token == request.token
    ).first()
    
    if not password_reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )
    
    # Check if already used
    if password_reset.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token already used"
        )
    
    # Check if expired
    if password_reset.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token expired. Please request a new one."
        )
    
    # Validate new password
    is_valid, message = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Update password
    user = db.query(User).filter(User.id == password_reset.user_id).first()
    user.hashed_password = hash_password(request.new_password)
    
    # Mark token as used
    password_reset.is_used = True
    password_reset.used_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Password reset successfully! You can now login with your new password."
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.
    """
    return UserResponse.from_orm(current_user)


@router.post("/profile-photo", response_model=UserResponse)
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload user profile photo.
    
    Args:
        file: Image file (max 5MB, jpg/jpeg/png/gif)
        
    Returns:
        Updated user information with new profile photo URL
    """
    # Create uploads directory if it doesn't exist
    UPLOAD_DIR = Path("uploads/profile_photos")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (jpg, jpeg, png, gif)"
        )
    
    # Validate file size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB"
        )
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'jpg'
    unique_filename = f"{current_user.id}_{uuid.uuid4()}.{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Delete old photo if exists
    if current_user.profile_photo_url:
        old_file_path = current_user.profile_photo_url.replace('/uploads/', 'uploads/')
        old_file = Path(old_file_path)
        if old_file.exists():
            try:
                old_file.unlink()
            except Exception as e:
                print(f"Could not delete old profile photo: {e}")
    
    # Save new file
    try:
        with open(file_path, 'wb') as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving file: {str(e)}"
        )
    
    # Update user record
    photo_url = f"/uploads/profile_photos/{unique_filename}"
    current_user.profile_photo_url = photo_url
    db.commit()
    db.refresh(current_user)
    
    return UserResponse.from_orm(current_user)


@router.delete("/profile-photo")
async def delete_profile_photo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete user profile photo.
    
    Returns:
        Success message
    """
    if not current_user.profile_photo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile photo to delete"
        )
    
    # Delete file from filesystem
    old_file_path = current_user.profile_photo_url.replace('/uploads/', 'uploads/')
    old_file = Path(old_file_path)
    if old_file.exists():
        try:
            old_file.unlink()
        except Exception as e:
            print(f"Could not delete profile photo file: {e}")
    
    # Update user record
    current_user.profile_photo_url = None
    db.commit()
    
    return {
        "message": "Profile photo deleted successfully"
    }


@router.post("/resend-verification")
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resend verification email to current user.
    """
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate new verification token
    verification_token = generate_verification_token()
    verification = EmailVerification(
        user_id=current_user.id,
        token=verification_token,
        expires_at=get_verification_expiry()
    )
    db.add(verification)
    db.commit()
    
    # Send verification email
    send_verification_email(current_user.email, current_user.full_name, verification_token)
    
    return {
        "message": "Verification email sent successfully"
    }
