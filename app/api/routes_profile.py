"""
User Profile & Health Profile Management
Routes for managing user profiles and health information
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.chat import HealthProfile, SearchHistory

router = APIRouter(prefix="/api/v1/user", tags=["User Profile"])


# ===== PYDANTIC MODELS =====

class HealthProfileCreate(BaseModel):
    """Model for creating health profile"""
    age: Optional[int] = Field(None, description="User age")
    gender: Optional[str] = Field(None, description="User gender")
    health_goals: Optional[str] = Field(None, description="Health goals (JSON string)")
    medical_conditions: Optional[str] = Field(None, description="Existing medical conditions (JSON string)")
    allergies: Optional[str] = Field(None, description="User allergies (JSON string)")
    medications: Optional[str] = Field(None, description="Current medications (JSON string)")
    preferences: Optional[str] = Field(None, description="User preferences (JSON string)")
    restrictions: Optional[str] = Field(None, description="Dietary restrictions (JSON string)")


class HealthProfileResponse(BaseModel):
    """Model for health profile response"""
    id: int
    user_id: int
    age: Optional[int]
    gender: Optional[str]
    health_goals: Optional[str]
    medical_conditions: Optional[str]
    allergies: Optional[str]
    medications: Optional[str]
    preferences: Optional[str]
    restrictions: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SearchHistoryItem(BaseModel):
    """Model for search history item"""
    id: int
    query: str
    search_type: str
    results_count: int
    searched_at: datetime

    class Config:
        from_attributes = True


class SearchHistoryResponse(BaseModel):
    """Model for search history response"""
    total: int
    searches: list[SearchHistoryItem]


# ===== HEALTH PROFILE ENDPOINTS =====

@router.get("/profile", response_model=HealthProfileResponse)
async def get_health_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's health profile.
    
    Returns:
        User's health profile or 404 if not created yet
    """
    profile = db.query(HealthProfile).filter(
        HealthProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Health profile not found. Create one first using POST /api/v1/user/profile"
        )
    
    return profile


@router.post("/profile", response_model=HealthProfileResponse)
async def create_or_update_health_profile(
    profile_data: HealthProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update health profile for current user.
    
    Args:
        profile_data: Health profile information
        
    Returns:
        Created or updated health profile
    """
    try:
        # Check if profile already exists
        existing = db.query(HealthProfile).filter(
            HealthProfile.user_id == current_user.id
        ).first()
        
        if existing:
            # Update existing profile
            for key, value in profile_data.dict(exclude_unset=True).items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new profile
            profile = HealthProfile(
                user_id=current_user.id,
                **profile_data.dict(exclude_unset=True)
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            return profile
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating/updating health profile: {str(e)}"
        )


@router.put("/profile", response_model=HealthProfileResponse)
async def update_health_profile(
    profile_data: HealthProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update health profile for current user.
    
    Args:
        profile_data: Updated health profile information
        
    Returns:
        Updated health profile
    """
    profile = db.query(HealthProfile).filter(
        HealthProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Health profile not found. Create one first using POST /api/v1/user/profile"
        )
    
    # Update fields
    for key, value in profile_data.dict(exclude_unset=True).items():
        setattr(profile, key, value)
    
    profile.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(profile)
    
    return profile


@router.delete("/profile")
async def delete_health_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete health profile for current user.
    
    Returns:
        Success message
    """
    profile = db.query(HealthProfile).filter(
        HealthProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Health profile not found"
        )
    
    db.delete(profile)
    db.commit()
    
    return {"message": "Health profile deleted successfully"}


# ===== SEARCH HISTORY ENDPOINTS =====

@router.get("/search-history", response_model=SearchHistoryResponse)
async def get_search_history(
    limit: int = 50,
    search_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's search history.
    
    Args:
        limit: Maximum number of searches to return (default 50)
        search_type: Filter by type: "medicine", "symptom", or None for all
        
    Returns:
        List of user's recent searches
    """
    query = db.query(SearchHistory).filter(
        SearchHistory.user_id == current_user.id
    )
    
    # Filter by type if specified
    if search_type:
        query = query.filter(SearchHistory.search_type == search_type)
    
    # Get total count
    total = query.count()
    
    # Get searches ordered by most recent
    searches = query.order_by(
        SearchHistory.timestamp.desc()
    ).limit(limit).all()
    
    return SearchHistoryResponse(
        total=total,
        searches=[SearchHistoryItem(
            id=s.id,
            query=s.search_query,
            search_type=s.search_type or "chat",
            results_count=s.results_count or 0,
            searched_at=s.timestamp
        ) for s in searches]
    )


@router.delete("/search-history")
async def clear_search_history(
    search_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear user's search history.
    
    Args:
        search_type: Clear only specific type ("medicine", "symptom") or all if None
        
    Returns:
        Number of searches deleted
    """
    query = db.query(SearchHistory).filter(
        SearchHistory.user_id == current_user.id
    )
    
    # Filter by type if specified
    if search_type:
        query = query.filter(SearchHistory.search_type == search_type)
    
    # Get count before deletion
    count = query.count()
    
    # Delete
    query.delete()
    db.commit()
    
    return {
        "message": f"Deleted {count} search history entries",
        "count": count
    }


@router.delete("/search-history/{search_id}")
async def delete_search_history_item(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific search history item.
    
    Args:
        search_id: ID of the search to delete
        
    Returns:
        Success message
    """
    search = db.query(SearchHistory).filter(
        SearchHistory.id == search_id,
        SearchHistory.user_id == current_user.id
    ).first()
    
    if not search:
        raise HTTPException(
            status_code=404,
            detail="Search history item not found"
        )
    
    db.delete(search)
    db.commit()
    
    return {"message": "Search history item deleted successfully"}
