"""
RAG Generator Module
Handles the Retrieval-Augmented Generation pipeline using:
- ChromaDB for vector storage
- Sentence Transformers for embeddings
- Google Gemini 1.5 for answer generation
"""

import os
from typing import List, Tuple
from dotenv import load_dotenv

# Note: Install these packages if encountering import errors:
# pip install chromadb sentence-transformers google-generativeai langchain

try:
    import google.generativeai as genai
    # Try new packages first
    try:
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        # Fallback to old packages
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceEmbeddings
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    print("Warning: Some RAG dependencies not installed. Run: pip install -r requirements.txt")

load_dotenv()

class MedChatRAG:
    """Main RAG pipeline for medical Q&A"""
    
    def __init__(self):
        if not IMPORTS_AVAILABLE:
            raise ImportError("Required packages not installed")
        
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_google_api_key_here":
            raise ValueError("Please set GEMINI_API_KEY in .env file")
        
        genai.configure(api_key=api_key)
        
        # Configure model with timeout settings
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config=generation_config
        )
        
        # Initialize embeddings model
        print("🔄 Loading embeddings model (first time may take a minute)...")
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print("✅ Embeddings model loaded")
        except Exception as e:
            print(f"⚠️ Warning: Could not load embeddings model: {e}")
            self.embeddings = None
        
        # Initialize ChromaDB
        chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
        
        if not self.embeddings:
            print("⚠️ Skipping ChromaDB initialization (no embeddings)")
            self.vectordb = None
            return
        
        try:
            self.vectordb = Chroma(
                persist_directory=chroma_dir,
                embedding_function=self.embeddings
            )
            print("✅ ChromaDB initialized")
        except Exception as e:
            print(f"⚠️ Warning: ChromaDB not initialized: {e}")
            self.vectordb = None
    
    def retrieve_context(self, query: str, max_results: int = 3) -> List[str]:
        """Retrieve relevant documents from vector database"""
        if not self.vectordb:
            return []
        
        try:
            # Use similarity_search directly on vectordb (works with all LangChain versions)
            docs = self.vectordb.similarity_search(query, k=max_results)
            return [doc.page_content for doc in docs]
        except Exception as e:
            print(f"Error retrieving documents: {e}")
            return []
    
    def generate_answer(self, query: str, context: List[str], chat_history: List[dict] = None) -> str:
        """Generate answer using Gemini with retrieved context and chat history"""
        
        # Prepare chat history if provided
        history_text = ""
        if chat_history and len(chat_history) > 0:
            history_text = "\n\nPrevious Conversation:\n"
            for msg in chat_history[-6:]:  # Last 3 exchanges
                role = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"
        
        # Prepare context text
        if context and len(context) > 0:
            # Priority 1: Use RAG data (local medical database)
            context_text = "\n\n".join([f"Source {i+1}: {c}" for i, c in enumerate(context)])
            prompt = f"""You are a medical information assistant. Answer the following question based on the provided medical data.{history_text}

Medical Context from Database:
{context_text}

Question: {query}

Instructions:
- Answer factually based ONLY on the provided context
- Use the medical information from the sources above
- Keep answers clear, detailed, and comprehensive
- Include relevant medical terminology when appropriate
- If this is a follow-up question, consider the previous conversation context
- Always recommend consulting healthcare professionals for medical advice

Answer:"""
        else:
            # Priority 2: Use Gemini AI directly (no local data available)
            prompt = f"""You are a medical information assistant. Answer the following medical question using your knowledge.{history_text}

Question: {query}

Instructions:
- Provide accurate, helpful medical information based on your training
- Keep answers clear, detailed, and comprehensive
- Cover relevant aspects (description, symptoms, causes, treatments, etc.)
- Use simple language that's easy to understand
- If this is a follow-up question, consider the previous conversation context
- Always recommend consulting healthcare professionals for medical advice
- Note: This information is for educational purposes only

Answer:"""
        
        try:
            # Always use standard Gemini generation (NO Google Search)
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
                return "The AI service is taking longer than expected. This might be due to high traffic. Please try again in a moment."
            elif "503" in error_msg or "connect" in error_msg.lower():
                return "Unable to connect to the AI service. Please check your internet connection and try again."
            else:
                return f"Error generating response: {error_msg}"
    
    def get_answer(self, query: str, max_results: int = 3, chat_history: List[dict] = None) -> Tuple[str, List[str]]:
        """
        Main method: Retrieve context and generate answer
        Returns: (answer, sources)
        """
        # Retrieve relevant context
        context = self.retrieve_context(query, max_results)
        
        # Generate answer with chat history
        answer = self.generate_answer(query, context, chat_history)
        
        return answer, context


# Global instance (singleton pattern)
_rag_instance = None

def get_rag_instance() -> MedChatRAG:
    """Get or create RAG instance"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = MedChatRAG()
    return _rag_instance


def get_medchat_answer(query: str, max_results: int = 3, chat_history: List[dict] = None) -> Tuple[str, List[str]]:
    """
    Convenience function for getting answers
    
    Args:
        query: User's medical question
        max_results: Number of context documents to retrieve
        chat_history: Previous conversation messages for context
    
    Returns:
        Tuple of (answer, sources)
    """
    try:
        rag = get_rag_instance()
        return rag.get_answer(query, max_results, chat_history)
    except Exception as e:
        error_msg = f"RAG system error: {str(e)}"
        return error_msg, []
