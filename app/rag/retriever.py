"""
Retriever Module
Handles document retrieval from ChromaDB
"""

import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

def create_vectordb(embeddings_model, persist_directory: str = None):
    """
    Create or load ChromaDB vector store
    
    Args:
        embeddings_model: Embeddings model for vector creation
        persist_directory: Directory to persist the database
    
    Returns:
        ChromaDB instance
    """
    if persist_directory is None:
        persist_directory = os.getenv("CHROMA_DIR", "./chroma_db")
    
    try:
        from langchain_community.vectorstores import Chroma
        
        vectordb = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings_model
        )
        return vectordb
    except ImportError:
        print("Error: chromadb not installed")
        print("Run: pip install chromadb langchain-community")
        return None
    except Exception as e:
        print(f"Error creating vector database: {e}")
        return None

def add_documents_to_vectordb(vectordb, documents: List):
    """
    Add documents to the vector database
    
    Args:
        vectordb: ChromaDB instance
        documents: List of documents to add
    """
    if not vectordb or not documents:
        return
    
    try:
        vectordb.add_documents(documents)
        vectordb.persist()
        print(f"Added {len(documents)} documents to vector database")
    except Exception as e:
        print(f"Error adding documents: {e}")

def retrieve_similar_documents(vectordb, query: str, k: int = 3) -> List[Dict]:
    """
    Retrieve similar documents for a query
    
    Args:
        vectordb: ChromaDB instance
        query: Search query
        k: Number of documents to retrieve
    
    Returns:
        List of similar documents with metadata
    """
    if not vectordb:
        return []
    
    try:
        # Use similarity_search directly instead of retriever
        docs = vectordb.similarity_search(query, k=k)
        
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata if hasattr(doc, 'metadata') else {}
            }
            for doc in docs
        ]
    except Exception as e:
        print(f"Error retrieving documents: {e}")
        return []


def get_retriever():
    """
    Get a retriever instance with ChromaDB and embeddings
    
    Returns:
        ChromaDB vectorstore instance (not retriever to avoid langchain.debug issue)
    """
    try:
        # Try new langchain packages first
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_chroma import Chroma
        except ImportError:
            # Fallback to old packages
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma
        
        # Initialize embeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Load ChromaDB
        persist_directory = os.getenv("CHROMA_DIR", "./chroma_db")
        vectordb = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )
        
        # Return vectordb directly (not as_retriever) to avoid langchain.debug issue
        return vectordb
        
    except Exception as e:
        print(f"Error creating retriever: {e}")
        raise
