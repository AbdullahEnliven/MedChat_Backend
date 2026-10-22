from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

# Import RAG generator
try:
    from app.rag.generator import get_medchat_answer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("Warning: RAG generator not available. Install dependencies.")

# Import authentication
try:
    from app.api.routes_auth import get_current_verified_user, get_current_user
    from app.models.user import User, ChatSession
    from app.core.database import get_db
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    print("Warning: Authentication not available.")
    # Define placeholder types
    class User:
        pass
    class ChatSession:
        pass
    def get_db():
        return None
    def get_current_verified_user():
        return None
    def get_current_user():
        return None

load_dotenv()

router = APIRouter(prefix="/api/v1", tags=["MedChat Core"])

# ===== REQUEST/RESPONSE MODELS =====

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Medical question to ask")
    max_results: Optional[int] = Field(3, ge=1, le=10, description="Number of context documents to retrieve")
    session_id: Optional[str] = Field("default", description="Session ID for conversation history")

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: Optional[List[str]] = []
    metadata: Optional[Dict] = {}

class HealthResponse(BaseModel):
    status: str
    message: str
    version: str = "1.0.0"

class TopicItem(BaseModel):
    id: int
    title: str
    category: str

class TopicsResponse(BaseModel):
    topics: List[TopicItem]
    count: int

# ===== ENDPOINTS =====

@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    current_user: Any = Depends(get_current_verified_user),
    db: Any = Depends(get_db)
):
    """
    🏥 Main endpoint for asking medical questions.
    
    **Requires**: Authentication (verified email)
    
    Uses RAG pipeline to:
    1. Retrieve relevant medical documents from ChromaDB
    2. Send context to Google Gemini 1.5 Pro
    3. Return a factual, well-informed medical answer
    
    **Fallback**: If no relevant data in ChromaDB, uses Gemini with Google Search.
    
    **Chat History**: Maintains conversation context per user and session in database.
    
    **Note**: This is for informational purposes only. Always consult healthcare professionals.
    """
    try:
        if not request.query or len(request.query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Check if RAG is available
        if not RAG_AVAILABLE:
            raise HTTPException(
                status_code=503, 
                detail="RAG system not available. Please install dependencies: pip install -r requirements.txt"
            )
        
        # Get user's chat history from database
        chat_history = []
        if AUTH_AVAILABLE and current_user and db:
            # Fetch last 20 messages for this session
            db_messages = db.query(ChatSession).filter(
                ChatSession.user_id == current_user.id,
                ChatSession.session_id == request.session_id
            ).order_by(ChatSession.created_at.desc()).limit(20).all()
            
            # Reverse to get chronological order
            db_messages.reverse()
            
            # Convert to chat history format
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in db_messages
            ]
        
        # Get answer from RAG pipeline with chat history
        answer, sources = get_medchat_answer(
            request.query, 
            max_results=request.max_results,
            chat_history=chat_history
        )
        
        # Save this exchange to database
        if AUTH_AVAILABLE and current_user and db:
            # Save user message
            user_message = ChatSession(
                user_id=current_user.id,
                session_id=request.session_id,
                role="user",
                content=request.query
            )
            db.add(user_message)
            
            # Save assistant message
            assistant_message = ChatSession(
                user_id=current_user.id,
                session_id=request.session_id,
                role="assistant",
                content=answer
            )
            db.add(assistant_message)
            
            db.commit()
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            metadata={
                "model": "gemini-2.5-flash",
                "num_sources": len(sources),
                "session_id": request.session_id,
                "history_length": len(chat_history)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    ✅ Backend health check endpoint
    
    Returns the current status of the MedChat backend.
    """
    api_key_configured = os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_API_KEY") != "your_google_api_key_here"
    
    return HealthResponse(
        status="ok" if api_key_configured else "warning",
        message="MedChat backend is healthy" if api_key_configured else "API key not configured",
        version="1.0.0"
    )


@router.get("/topics", response_model=TopicsResponse)
async def get_topics():
    """
    📚 Get available medical topics
    
    Returns a list of all medical topics stored in the vector database.
    
    **Note**: This will return sample topics until medical data is loaded.
    """
    # Sample topics (replace with actual ChromaDB metadata query when data is loaded)
    sample_topics = [
        TopicItem(id=1, title="Migraine", category="Neurological"),
        TopicItem(id=2, title="Asthma", category="Respiratory"),
        TopicItem(id=3, title="Diabetes", category="Endocrine"),
        TopicItem(id=4, title="Hypertension", category="Cardiovascular"),
        TopicItem(id=5, title="Influenza (Flu)", category="Infectious"),
        TopicItem(id=6, title="Arthritis", category="Musculoskeletal"),
        TopicItem(id=7, title="Depression", category="Mental Health"),
        TopicItem(id=8, title="Allergies", category="Immune System"),
    ]
    
    # TODO: Query ChromaDB for actual topics when data is loaded
    # if vectordb:
    #     topics = vectordb.get_all_unique_metadata("topic")
    
    return TopicsResponse(
        topics=sample_topics,
        count=len(sample_topics)
    )


@router.get("/status")
async def get_status():
    """
    🔍 Check RAG system status
    
    Returns detailed information about the RAG pipeline components.
    """
    api_key_configured = os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_API_KEY") != "your_google_api_key_here"
    chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
    chroma_exists = os.path.exists(chroma_dir)
    
    return {
        "rag_available": RAG_AVAILABLE,
        "api_key_configured": api_key_configured,
        "vectordb_status": "initialized" if chroma_exists else "not_initialized",
        "vectordb_path": chroma_dir,
        "llm_model": "gemini-2.5-flash",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "status": "ready" if (RAG_AVAILABLE and api_key_configured) else "configuration_needed"
    }
