"""
Configuration Module
Handles application settings and environment variables
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment"""
    
    # Application
    app_name: str = "MedChat Backend"
    app_url: str = "http://localhost:8000"
    debug: bool = True
    
    # Security
    secret_key: str = "your-secret-key-please-change-to-a-secure-random-string-in-production"
    access_token_expire_minutes: int = 10080  # 7 days
    
    # Google Gemini API
    GEMINI_API_KEY: str = "your_google_api_key_here"
    
    # Database
    DATABASE_URL: str = "postgresql://username:password@localhost:5432/medchat_db"
    
    # ChromaDB
    CHROMA_DIR: str = "./chroma_db"
    
    # Database Path
    DB_PATH: str = "./database/medchat.db"
    
    # Logs Path
    LOGS_DIR: str = "./logs"
    
    # Embedding Model
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # API Settings
    MAX_QUERY_LENGTH: int = 500
    DEFAULT_MAX_RESULTS: int = 3
    
    # Email Settings
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = "your-email@gmail.com"
    smtp_password: str = "your-gmail-app-password"
    from_email: str = "your-email@gmail.com"
    from_name: str = "MedChat Support"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create global settings instance
settings = get_settings()
