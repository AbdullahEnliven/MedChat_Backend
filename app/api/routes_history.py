"""
Chat History Routes - Save and retrieve conversations
Routes: POST /chat/save, GET /chat/history/{user_id}
Purpose: Users can save and retrieve previous chats
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime, timedelta

try:
    from sqlalchemy.orm import Session
    from app.core.database import get_db
    from app.models.user import User, ChatSession
    from app.models.chat import SavedTopic
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    from typing import TYPE_CHECKING
    
    # Use type alias for Session when SQLAlchemy is not available
    if TYPE_CHECKING:
        from sqlalchemy.orm import Session
    else:
        Session = Any
    
    # Create a dummy get_db that returns an error
    async def get_db():
        """Dummy database dependency when DB is not available"""
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Install PostgreSQL and set DATABASE_URL to use chat history."
        )
        yield None  # This makes it a generator like the real get_db

router = APIRouter(prefix="/api/v1/chat", tags=["Chat History"])


class SaveChatRequest(BaseModel):
    """Request model for saving a chat"""
    user_id: str = Field(..., description="Unique user identifier")
    query: str = Field(..., description="User's question")
    answer: str = Field(..., description="AI's response")
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID")
    sources: Optional[List[str]] = Field(None, description="Source documents")


class ChatMessage(BaseModel):
    """A single chat message"""
    id: int
    query: str
    answer: str
    timestamp: str
    rating: Optional[int] = None
    sources: Optional[List[str]] = None


class ConversationSummary(BaseModel):
    """Summary of a conversation"""
    id: int
    title: str
    message_count: int
    created_at: str
    updated_at: str
    is_bookmarked: bool
    preview: str  # First message preview


class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""
    user_id: str
    total_conversations: int
    conversations: List[ConversationSummary]


class RateChatRequest(BaseModel):
    """Request model for rating a chat"""
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback: Optional[str] = Field(None, description="Optional feedback text")


@router.post("/save")
async def save_chat(request: SaveChatRequest, db: Session = Depends(get_db)):
    """
    Save a chat conversation.
    
    Args:
        request: Chat save request with user_id, query, answer
        db: Database session
        
    Returns:
        Success message with chat ID
    """
    if not DB_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Set up database to use chat history feature."
        )
    
    try:
        # Parse user_id as integer
        try:
            user_id_int = int(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")
        
        # Get user
        user = db.query(User).filter(User.id == user_id_int).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate session ID if not provided
        import uuid
        session_id = request.conversation_id if request.conversation_id else str(uuid.uuid4())
        
        # Save user message
        user_message = ChatSession(
            user_id=user_id_int,
            session_id=str(session_id),
            role='user',
            content=request.query
        )
        db.add(user_message)
        
        # Save assistant message
        assistant_message = ChatSession(
            user_id=user_id_int,
            session_id=str(session_id),
            role='assistant',
            content=request.answer
        )
        db.add(assistant_message)
        
        db.commit()
        db.refresh(assistant_message)
        
        return {
            "message": "Chat saved successfully",
            "chat_id": assistant_message.id,
            "session_id": session_id,
            "timestamp": assistant_message.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error saving chat: {str(e)}"
        )


@router.get("/history/{user_id}")
async def get_chat_history(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get chat history for a user.
    
    Args:
        user_id: User identifier (integer ID)
        limit: Maximum number of messages to return
        db: Database session
        
    Returns:
        List of user's chat messages grouped by session
    """
    if not DB_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Database not configured."
        )
    
    try:
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "user_id": user_id,
                "total_messages": 0,
                "sessions": []
            }
        
        # Get chat sessions
        chat_messages = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(
            ChatSession.created_at.desc()
        ).limit(limit * 2).all()  # * 2 because user + assistant messages
        
        # Group messages by session_id
        from collections import defaultdict
        sessions_dict = defaultdict(list)
        
        for msg in chat_messages:
            sessions_dict[msg.session_id].append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat()
            })
        
        # Build sessions list
        sessions = []
        for session_id, messages in list(sessions_dict.items())[:limit]:
            # Sort messages by timestamp
            messages.sort(key=lambda x: x['timestamp'])
            
            # Get preview from first user message
            preview = next((m['content'][:100] for m in messages if m['role'] == 'user'), 'No messages')
            if len(preview) == 100:
                preview += "..."
            
            sessions.append({
                "session_id": session_id,
                "message_count": len(messages),
                "preview": preview,
                "messages": messages
            })
        
        return {
            "user_id": user_id,
            "total_messages": len(chat_messages),
            "sessions": sessions
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving chat history: {str(e)}"
        )


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Get all messages in a specific conversation.
    
    Args:
        conversation_id: Conversation ID
        db: Database session
        
    Returns:
        All messages in the conversation
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = db.query(ChatHistory).filter(
            ChatHistory.conversation_id == conversation_id
        ).order_by(ChatHistory.timestamp.asc()).all()
        
        import json
        chat_messages = []
        for msg in messages:
            sources = json.loads(msg.sources) if msg.sources else None
            chat_messages.append(ChatMessage(
                id=msg.id,
                query=msg.query,
                answer=msg.answer,
                timestamp=msg.timestamp.isoformat(),
                rating=msg.rating,
                sources=sources
            ))
        
        return {
            "conversation_id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "messages": chat_messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversation: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: int, user_id: str, db: Session = Depends(get_db)):
    """
    Delete a conversation and all its messages.
    
    Args:
        conversation_id: Conversation ID to delete
        user_id: User ID for verification
        db: Database session
        
    Returns:
        Success message
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        db.delete(conversation)
        db.commit()
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting conversation: {str(e)}"
        )


@router.post("/rate/{chat_id}")
async def rate_chat(
    chat_id: int,
    request: RateChatRequest,
    db: Session = Depends(get_db)
):
    """
    Rate a chat message.
    
    Args:
        chat_id: Chat message ID
        request: Rating and optional feedback
        db: Database session
        
    Returns:
        Success message
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    try:
        chat = db.query(ChatHistory).filter(ChatHistory.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        chat.rating = request.rating
        if request.feedback:
            chat.feedback = request.feedback
        
        db.commit()
        
        return {"message": "Rating saved successfully", "rating": request.rating}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error saving rating: {str(e)}"
        )


@router.post("/bookmark/{conversation_id}")
async def bookmark_conversation(
    conversation_id: int,
    user_id: str,
    bookmarked: bool = True,
    db: Session = Depends(get_db)
):
    """
    Bookmark or unbookmark a conversation.
    
    Args:
        conversation_id: Conversation ID
        user_id: User ID for verification
        bookmarked: True to bookmark, False to unbookmark
        db: Database session
        
    Returns:
        Success message
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conversation.is_bookmarked = bookmarked
        db.commit()
        
        action = "bookmarked" if bookmarked else "unbookmarked"
        return {"message": f"Conversation {action} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating bookmark: {str(e)}"
        )


@router.get("/search/{user_id}")
async def search_chat_history(
    user_id: str,
    query: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Search through user's chat history.
    
    Args:
        user_id: User ID
        query: Search query
        limit: Maximum results
        db: Database session
        
    Returns:
        Matching chat messages
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    try:
        # Search in queries and answers
        search_pattern = f"%{query}%"
        messages = db.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            (ChatHistory.query.ilike(search_pattern) | ChatHistory.answer.ilike(search_pattern))
        ).order_by(ChatHistory.timestamp.desc()).limit(limit).all()
        
        import json
        results = []
        for msg in messages:
            sources = json.loads(msg.sources) if msg.sources else None
            results.append({
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "query": msg.query,
                "answer": msg.answer[:200] + ("..." if len(msg.answer) > 200 else ""),
                "timestamp": msg.timestamp.isoformat(),
                "sources": sources
            })
        
        return {
            "query": query,
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chat history: {str(e)}"
        )
