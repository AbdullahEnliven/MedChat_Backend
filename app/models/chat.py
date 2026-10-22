"""
Extended Chat Models
Additional models for conversations, bookmarks, health profiles
Note: User and ChatSession models are in app/models/user.py
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class SavedTopic(Base):
    """Saved topics/bookmarks for quick access"""
    __tablename__ = "saved_topics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_name = Column(String(500), nullable=False)
    topic_category = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    saved_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SavedTopic(id={self.id}, topic={self.topic_name})>"


class HealthProfile(Base):
    """User health profile for personalized recommendations"""
    __tablename__ = "health_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    health_goals = Column(Text, nullable=True)  # JSON string
    medical_conditions = Column(Text, nullable=True)  # JSON string
    allergies = Column(Text, nullable=True)  # JSON string
    medications = Column(Text, nullable=True)  # JSON string
    preferences = Column(Text, nullable=True)  # JSON string
    restrictions = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<HealthProfile(user_id={self.user_id}, age={self.age})>"


class SearchHistory(Base):
    """Search history for analytics and recommendations"""
    __tablename__ = "search_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    search_query = Column(Text, nullable=False)
    search_type = Column(String(100), nullable=True)  # 'chat', 'medicine', 'symptom', etc.
    results_count = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(50), nullable=True)
    
    def __repr__(self):
        return f"<SearchHistory(id={self.id}, query={self.search_query[:30]})>"
