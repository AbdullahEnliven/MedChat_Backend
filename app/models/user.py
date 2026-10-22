"""
User Authentication Models
Handles user accounts, authentication, and password reset
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.core.database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Personal Information
    gender = Column(String(20), nullable=True)  # 'male', 'female', 'other', 'prefer_not_to_say'
    date_of_birth = Column(Date, nullable=True)  # Birthday
    age = Column(Integer, nullable=True)  # Calculated from date_of_birth
    profile_photo_url = Column(String(500), nullable=True)  # Profile photo URL
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.full_name})>"


class ChatSession(Base):
    """User chat history - each user has their own separate chat sessions"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    
    # Chat message
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="chat_sessions")
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, role={self.role})>"


class PasswordReset(Base):
    """Password reset tokens"""
    __tablename__ = "password_resets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    
    # Status
    is_used = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="password_resets")
    
    def __repr__(self):
        return f"<PasswordReset(id={self.id}, user_id={self.user_id}, is_used={self.is_used})>"


class EmailVerification(Base):
    """Email verification tokens"""
    __tablename__ = "email_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    
    # Status
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<EmailVerification(id={self.id}, user_id={self.user_id}, is_verified={self.is_verified})>"
