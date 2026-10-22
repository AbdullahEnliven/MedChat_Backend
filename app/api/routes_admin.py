"""
Admin Routes
Admin panel for user management and monitoring
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.user import User, ChatSession
from app.api.routes_auth import get_current_user
from app.utils.auth import hash_password

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# Pydantic Models
class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_chats: int
    
    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    total_users: int
    verified_users: int
    active_users: int
    total_chats: int
    users_today: int
    users_this_week: int
    users_this_month: int


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_admin: Optional[bool] = None


class CreateAdminRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    secret_key: str  # Security measure to prevent unauthorized admin creation


class CreateAdminResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_admin: bool
    is_verified: bool
    is_active: bool
    created_at: datetime
    message: str


# Dependency to verify admin access
async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verify that the current user is an admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user


@router.post("/create-admin", response_model=CreateAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_account(
    request: CreateAdminRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new admin account (Public endpoint with secret key protection)
    
    This endpoint allows creating the first admin account or additional admins
    using a secret key for security.
    
    **Secret Key:** Use the value from your .env file's SECRET_KEY
    
    - **email**: Admin email address
    - **full_name**: Admin full name
    - **password**: Strong password (min 8 chars, uppercase, lowercase, number, special char)
    - **secret_key**: Secret key from environment (for security)
    """
    from app.core.config import settings
    from app.utils.auth import validate_password_strength
    
    # Verify secret key
    if request.secret_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key. Admin creation not authorized."
        )
    
    # Validate password strength
    is_valid, message = validate_password_strength(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password validation failed: {message}"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{request.email}' already exists"
        )
    
    # Create new admin user
    hashed_password = hash_password(request.password)
    
    admin_user = User(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hashed_password,
        is_admin=True,
        is_verified=True,  # Auto-verify admin
        is_active=True
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    return CreateAdminResponse(
        id=admin_user.id,
        email=admin_user.email,
        full_name=admin_user.full_name,
        is_admin=admin_user.is_admin,
        is_verified=admin_user.is_verified,
        is_active=admin_user.is_active,
        created_at=admin_user.created_at,
        message="Admin account created successfully! You can now login with these credentials."
    )


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    is_verified: Optional[bool] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get all users (Admin only)
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **search**: Search by email or name
    - **is_verified**: Filter by verification status
    - **is_active**: Filter by active status
    """
    query = db.query(User)
    
    # Apply filters
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | 
            (User.full_name.ilike(f"%{search}%"))
        )
    
    if is_verified is not None:
        query = query.filter(User.is_verified == is_verified)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Apply pagination
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    
    # Add chat count to each user
    result = []
    for user in users:
        chat_count = db.query(func.count(ChatSession.id)).filter(
            ChatSession.user_id == user.id
        ).scalar()
        
        user_dict = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin,
            "created_at": user.created_at,
            "last_login": user.last_login,
            "total_chats": chat_count or 0
        }
        result.append(UserResponse(**user_dict))
    
    return result


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Get user statistics (Admin only)"""
    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    total_users = db.query(func.count(User.id)).scalar() or 0
    verified_users = db.query(func.count(User.id)).filter(User.is_verified == True).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_chats = db.query(func.count(ChatSession.id)).scalar() or 0
    
    users_today = db.query(func.count(User.id)).filter(
        func.date(User.created_at) == today
    ).scalar() or 0
    
    users_this_week = db.query(func.count(User.id)).filter(
        User.created_at >= week_ago
    ).scalar() or 0
    
    users_this_month = db.query(func.count(User.id)).filter(
        User.created_at >= month_ago
    ).scalar() or 0
    
    return UserStatsResponse(
        total_users=total_users,
        verified_users=verified_users,
        active_users=active_users,
        total_chats=total_chats,
        users_today=users_today,
        users_this_week=users_this_week,
        users_this_month=users_this_month
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Get specific user details (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    chat_count = db.query(func.count(ChatSession.id)).filter(
        ChatSession.user_id == user.id
    ).scalar() or 0
    
    user_dict = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "total_chats": chat_count
    }
    
    return UserResponse(**user_dict)


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Update user details (Admin only)
    
    Can update:
    - is_active: Activate/deactivate user
    - is_verified: Mark email as verified
    - is_admin: Grant/revoke admin privileges
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deactivating themselves
    if user_id == current_admin.id and update_data.is_active == False:
        raise HTTPException(
            status_code=400, 
            detail="Cannot deactivate your own account"
        )
    
    # Update fields
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    if update_data.is_verified is not None:
        user.is_verified = update_data.is_verified
    if update_data.is_admin is not None:
        user.is_admin = update_data.is_admin
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return {
        "message": "User updated successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin
        }
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Delete a user (Admin only)
    
    This will also delete all associated data:
    - Chat sessions
    - Password reset tokens
    - Email verification tokens
    """
    # Prevent admin from deleting themselves
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_email = user.email
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user_email} deleted successfully"}


@router.post("/create-admin")
async def create_admin_user(
    email: EmailStr,
    full_name: str,
    password: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Create a new admin user (Admin only)"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new admin user
    new_admin = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        is_active=True,
        is_verified=True,
        is_admin=True
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    return {
        "message": "Admin user created successfully",
        "user": {
            "id": new_admin.id,
            "email": new_admin.email,
            "full_name": new_admin.full_name,
            "is_admin": new_admin.is_admin
        }
    }
