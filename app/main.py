"""
MedChat Backend API
FastAPI application for medical information chatbot with RAG, authentication, and advanced features
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

# Import routers
from app.api.routes import router as main_router
from app.api.routes_auth import router as auth_router
from app.api.routes_admin import router as admin_router
from app.api.routes_medicine import router as medicine_router
from app.api.routes_symptom import router as symptom_router
from app.api.routes_tips import router as tips_router
from app.api.routes_voice import router as voice_router
from app.api.routes_history import router as history_router
from app.api.routes_profile import router as profile_router
from app.api.routes_chat import router as chat_router

# Database
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    print("Starting MedChat Backend...")
    
    # Initialize database
    try:
        init_db()
    except Exception as e:
        print(f"Database initialization failed: {e}")
    
    print("MedChat Backend ready!")
    
    yield
    
    print("Shutting down MedChat Backend...")


# Create FastAPI app
app = FastAPI(
    title="MedChat Backend API",
    description="Medical chatbot with RAG, OCR, symptom checker, and health tips",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update in production: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "profile_photos").mkdir(exist_ok=True)

# Mount static files for serving uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API routers
app.include_router(main_router)       # /api/v1/ask, /health, /topics
app.include_router(chat_router)       # /api/v1/chat/ask, /chat/query
app.include_router(auth_router)       # /api/v1/auth/*
app.include_router(admin_router)      # /api/v1/admin/*
app.include_router(medicine_router)   # /api/v1/medicine/*
app.include_router(symptom_router)    # /api/v1/symptom/*
app.include_router(tips_router)       # /api/v1/tips/*
app.include_router(voice_router)      # /api/v1/voice/*
app.include_router(history_router)    # /api/v1/history/*
app.include_router(profile_router)    # /api/v1/user/*


@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "name": "MedChat Backend API",
        "version": "2.0.0",
        "status": "healthy",
        "features": [
            "Smart Health Chat (RAG)",
            "User Authentication",
            "Admin Panel",
            "Medicine Scanner (OCR)",
            "Symptom Checker",
            "Health Tips",
            "Voice Input",
            "Chat History"
        ],
        "documentation": {
            "interactive": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0"
    }
