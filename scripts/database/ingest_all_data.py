"""
Complete Data Ingestion Pipeline for MedChat
Downloads and loads REAL medical data into ChromaDB:
1. MedlinePlus Health Topics (1000+ topics) - FREE, public domain
2. DrugBank Open Data (14,000+ drugs) - FREE for non-commercial use

NO DUMMY DATA - ALL REAL MEDICAL INFORMATION

Usage:
    python ingest_all_data.py              # Download and load everything
    python ingest_all_data.py --medlineplus-only   # Only health topics
    python ingest_all_data.py --drugbank-only      # Only medicines (requires manual download)
"""

import sys
from pathlib import Path
import argparse

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


def load_medlineplus_data():
    """Download and load MedlinePlus health topics"""
    
    print("\n" + "="*70)
    print("🏥 LOADING MEDLINEPLUS HEALTH TOPICS (REAL DATA)")
    print("="*70)
    print("Source: https://medlineplus.gov/xml.html")
    print("License: Public Domain (U.S. Government)")
    print("="*70 + "\n")
    
    # Import the ingestion module
    from app.data.ingest_medlineplus import download_medlineplus_data, parse_medlineplus_xml, format_for_embeddings
    
    try:
        # Download XML
        xml_path = download_medlineplus_data()
        
        # Parse XML
        topics = parse_medlineplus_xml(xml_path)
        print(f"\n📊 Parsed {len(topics)} health topics from MedlinePlus")
        
        # Format for embeddings
        documents_data = format_for_embeddings(topics)
        
        # Convert to LangChain Document objects
        print("\n🔄 Converting to Document objects...")
        documents = []
        for doc_data in documents_data:
            doc = Document(
                page_content=doc_data['content'],
                metadata=doc_data['metadata']
            )
            documents.append(doc)
        
        print(f"✅ Created {len(documents)} documents from MedlinePlus")
        return documents
        
    except Exception as e:
        print(f"\n❌ Error loading MedlinePlus: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_drugbank_data():
    """Load DrugBank drug information (requires manual download)"""
    
    print("\n" + "="*70)
    print("💊 LOADING DRUGBANK MEDICINES (REAL DATA)")
    print("="*70)
    print("Source: https://go.drugbank.com/releases/latest")
    print("License: CC BY-NC 4.0 (Non-commercial use)")
    print("="*70 + "\n")
    
    from app.data.ingest_drugbank import parse_drugbank_xml, format_for_embeddings
    
    # Check if DrugBank XML exists
    data_dir = Path("app/data/downloads/drugbank")
    xml_path = data_dir / "full database.xml"
    
    if not xml_path.exists():
        print("❌ DrugBank XML file not found!")
        print("\n📥 MANUAL DOWNLOAD REQUIRED:")
        print("=" * 70)
        print("1. Visit: https://go.drugbank.com/releases/latest")
        print("2. Create FREE account (click 'Go to Downloads')")
        print("3. Download 'DrugBank Open Data' XML")
        print("   File: 'drugbank_all_full_database.xml.zip' (~100MB)")
        print("4. Extract the XML file")
        print(f"5. Place it at: {xml_path}")
        print("\n⚖️  License: CC BY-NC 4.0")
        print("   - FREE for research, education, testing")
        print("   - Must credit DrugBank")
        print("   - Commercial use requires paid license")
        print("=" * 70)
        print("\n💡 For now, continuing with MedlinePlus data only...")
        return []
    
    try:
        # Parse DrugBank XML
        print(f"📖 Parsing DrugBank XML from {xml_path}...")
        drugs = parse_drugbank_xml(xml_path, limit=None)  # Load ALL drugs
        print(f"\n📊 Parsed {len(drugs)} drugs from DrugBank")
        
        # Format for embeddings
        documents_data = format_for_embeddings(drugs)
        
        # Convert to LangChain Document objects
        print("\n🔄 Converting to Document objects...")
        documents = []
        for doc_data in documents_data:
            doc = Document(
                page_content=doc_data['content'],
                metadata=doc_data['metadata']
            )
            documents.append(doc)
        
        print(f"✅ Created {len(documents)} documents from DrugBank")
        return documents
        
    except Exception as e:
        print(f"\n❌ Error loading DrugBank: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_into_chromadb(documents: list, batch_size: int = 100):
    """Load documents into ChromaDB with embeddings"""
    
    if not documents:
        print("\n⚠️  No documents to load!")
        return None
    
    print("\n" + "="*70)
    print("🔄 LOADING INTO CHROMADB")
    print("="*70)
    
    # Initialize embeddings model
    print("\n📦 Loading embeddings model...")
    print("   Model: sentence-transformers/all-MiniLM-L6-v2")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    print("✅ Embeddings model loaded")
    
    # Connect to ChromaDB
    print("\n🔗 Connecting to ChromaDB...")
    persist_directory = "./chroma_db"
    vectordb = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    print(f"✅ Connected to ChromaDB at {persist_directory}")
    
    # Add documents in batches
    print(f"\n📥 Adding {len(documents)} documents in batches of {batch_size}...")
    total_batches = (len(documents) + batch_size - 1) // batch_size
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        try:
            vectordb.add_documents(batch)
            print(f"   ✅ Batch {batch_num}/{total_batches} added ({len(batch)} documents)")
        except Exception as e:
            print(f"   ❌ Error in batch {batch_num}: {e}")
    
    print("\n✅ All documents loaded into ChromaDB!")
    
    # Get statistics
    try:
        collection = vectordb._collection
        total_count = collection.count()
        print(f"\n📊 Total documents in database: {total_count}")
    except:
        print(f"\n📊 Documents added: {len(documents)}")
    
    return vectordb


def test_retrieval(vectordb):
    """Test retrieval with sample queries"""
    
    print("\n" + "="*70)
    print("🧪 TESTING RETRIEVAL")
    print("="*70)
    
    test_queries = [
        ("What is diabetes?", "health"),
        ("Tell me about asthma symptoms", "health"),
        ("What is Panadol used for?", "medicine"),
        ("Ibuprofen side effects", "medicine"),
        ("Blood pressure medication", "medicine"),
    ]
    
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    
    for query, query_type in test_queries:
        print(f"\n🔍 Query: '{query}' (Type: {query_type})")
        
        try:
            results = retriever.invoke(query)
            
            if results:
                for i, doc in enumerate(results, 1):
                    title = doc.metadata.get("title") or doc.metadata.get("drug_name", "Unknown")
                    source = doc.metadata.get("source", "Unknown")
                    print(f"   {i}. {title} (Source: {source})")
            else:
                print("   ⚠️  No results found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")


def main():
    """Main ingestion pipeline"""
    
    parser = argparse.ArgumentParser(
        description='Download and load real medical data into ChromaDB'
    )
    parser.add_argument('--medlineplus-only', action='store_true',
                        help='Load only MedlinePlus health topics')
    parser.add_argument('--drugbank-only', action='store_true',
                        help='Load only DrugBank medicines')
    parser.add_argument('--clear', action='store_true',
                        help='Clear existing ChromaDB before loading')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🏥 MEDCHAT DATA INGESTION PIPELINE")
    print("="*70)
    print("Loading REAL medical data from official sources:")
    print("  • MedlinePlus: Public health topics (NIH)")
    print("  • DrugBank: Drug/medicine information")
    print("="*70)
    
    # Clear database if requested
    if args.clear:
        print("\n🗑️  Clearing existing ChromaDB...")
        import shutil
        db_path = Path("./chroma_db")
        if db_path.exists():
            shutil.rmtree(db_path)
            print("✅ ChromaDB cleared")
    
    all_documents = []
    
    # Load MedlinePlus
    if not args.drugbank_only:
        medlineplus_docs = load_medlineplus_data()
        all_documents.extend(medlineplus_docs)
    
    # Load DrugBank
    if not args.medlineplus_only:
        drugbank_docs = load_drugbank_data()
        all_documents.extend(drugbank_docs)
    
    # Load into ChromaDB
    if all_documents:
        vectordb = load_into_chromadb(all_documents)
        
        if vectordb:
            # Test retrieval
            test_retrieval(vectordb)
            
            print("\n" + "="*70)
            print("✅ DATA INGESTION COMPLETE!")
            print("="*70)
            print(f"\n📊 Summary:")
            print(f"   • Total documents loaded: {len(all_documents)}")
            print(f"   • Database: ./chroma_db")
            print(f"\n💡 Next steps:")
            print(f"   • Start server: python run.py")
            print(f"   • Test health Q&A: http://localhost:8000/ask")
            print(f"   • Test medicine: http://localhost:8000/api/v1/medicine/aspirin")
            print(f"   • API docs: http://localhost:8000/docs")
            print("="*70 + "\n")
    else:
        print("\n❌ No data loaded! Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
