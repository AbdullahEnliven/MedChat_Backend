"""
Chat Routes - Alias for main RAG ask endpoint
Provides /chat/ask endpoint for frontend compatibility
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

# Import from main routes
from app.api.routes import (
    QueryRequest, 
    QueryResponse, 
    ask_question,
    get_current_verified_user,
    get_db
)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


@router.post("/ask", response_model=QueryResponse)
async def chat_ask(
    request: QueryRequest,
    current_user: Any = Depends(get_current_verified_user),
    db: Any = Depends(get_db)
):
    """
    🏥 Chat endpoint - Ask medical questions
    
    **Alias for /api/v1/ask endpoint**
    
    Requires authentication (verified email).
    
    Uses RAG pipeline to:
    1. Retrieve relevant medical documents from ChromaDB
    2. Send context to Google Gemini 1.5 Pro
    3. Return a factual, well-informed medical answer
    
    **Note**: This is for informational purposes only. Always consult healthcare professionals.
    """
    # Call the main ask_question function
    return await ask_question(request, current_user, db)


# Alternative endpoint for compatibility
@router.post("/query", response_model=QueryResponse)
async def chat_query(
    request: QueryRequest,
    current_user: Any = Depends(get_current_verified_user),
    db: Any = Depends(get_db)
):
    """
    🏥 Chat query endpoint - Alternative to /ask
    
    Same functionality as /chat/ask
    """
    return await ask_question(request, current_user, db)
