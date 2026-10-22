"""
Database Module
PostgreSQL database configuration and session management
All models inherit from a single Base instance
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost:5432/medchat_db")

# Try to create engine, but don't fail if PostgreSQL is not available
try:
    # SQLAlchemy engine (echo=False for production, set to True for debugging)
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=10,  # Connection pool size
        max_overflow=20  # Max connections beyond pool_size
    )
    
    # Session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    DB_AVAILABLE = True
except Exception as e:
    print(f"Warning: Database not available: {e}")
    print("   Server will run without database features (auth, chat history)")
    SessionLocal = None
    engine = None
    DB_AVAILABLE = False

# Single Base class for all models
Base = declarative_base()


def get_db():
    """
    Dependency for database sessions in FastAPI endpoints
    Usage: db: Session = Depends(get_db)
    """
    if not DB_AVAILABLE or not SessionLocal:
        yield None
        return
        
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables
    Creates all tables defined in models that inherit from Base
    """
    try:
        # Import all models to ensure they're registered with Base
        from app.models.user import User, ChatSession, PasswordReset, EmailVerification
        from app.models.chat import SavedTopic, HealthProfile, SearchHistory
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("Database initialized successfully!")
        print(f"   Tables created: {', '.join(Base.metadata.tables.keys())}")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("   Ensure PostgreSQL is running and DATABASE_URL is correct")
        raise


def drop_all_tables():
    """
    Drop all database tables (use with caution!)
    Only for development/testing
    """
    Base.metadata.drop_all(bind=engine)
    print("WARNING: All tables dropped")
