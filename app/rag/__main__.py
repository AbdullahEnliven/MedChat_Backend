"""
Embedder Module - Main Entry Point
Run with: python -m app.rag.embedder

This script:
1. Loads medical data from data/ directory
2. Processes and chunks documents
3. Creates embeddings using Sentence Transformers
4. Stores vectors in ChromaDB
"""

import sys
import os
from pathlib import Path
from typing import List
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

def create_sample_medical_data():
    """Create sample medical documents for testing"""
    from langchain_core.documents import Document
    
    sample_docs = [
        Document(
            page_content="""
            Migraine: A migraine is a type of headache characterized by intense, throbbing pain, 
            usually on one side of the head. Common symptoms include sensitivity to light and sound, 
            nausea, and vomiting. Visual disturbances (aura) may occur before the headache. 
            Triggers include stress, certain foods, hormonal changes, and lack of sleep.
            Treatment includes pain relievers, anti-nausea medications, and preventive medications.
            """,
            metadata={"source": "medlineplus", "topic": "Migraine", "category": "Neurological"}
        ),
        Document(
            page_content="""
            Asthma: Asthma is a chronic respiratory condition causing inflammation and narrowing of airways.
            Symptoms include wheezing, shortness of breath, chest tightness, and coughing, especially at night.
            Common triggers include allergens, exercise, cold air, and respiratory infections.
            Treatment involves inhalers (bronchodilators and corticosteroids) and avoiding triggers.
            """,
            metadata={"source": "medlineplus", "topic": "Asthma", "category": "Respiratory"}
        ),
        Document(
            page_content="""
            Diabetes Type 2: A chronic condition affecting how the body processes blood sugar (glucose).
            Symptoms include increased thirst, frequent urination, fatigue, blurred vision, and slow wound healing.
            Risk factors include obesity, sedentary lifestyle, family history, and age over 45.
            Management includes diet, exercise, blood sugar monitoring, and medications (metformin, insulin).
            """,
            metadata={"source": "medlineplus", "topic": "Diabetes", "category": "Endocrine"}
        ),
        Document(
            page_content="""
            Hypertension (High Blood Pressure): A condition where blood pressure is consistently too high.
            Often called the "silent killer" because it usually has no symptoms until serious complications develop.
            Complications include heart disease, stroke, kidney damage, and vision problems.
            Treatment includes lifestyle changes (diet, exercise, weight loss) and medications (ACE inhibitors, diuretics).
            """,
            metadata={"source": "medlineplus", "topic": "Hypertension", "category": "Cardiovascular"}
        ),
        Document(
            page_content="""
            Influenza (Flu): A contagious respiratory illness caused by influenza viruses.
            Symptoms include fever, cough, sore throat, body aches, headache, and fatigue.
            Spread through respiratory droplets when infected people cough, sneeze, or talk.
            Prevention includes annual flu vaccination and good hygiene practices.
            Treatment includes rest, fluids, and antiviral medications if started early.
            """,
            metadata={"source": "medlineplus", "topic": "Influenza", "category": "Infectious"}
        ),
        Document(
            page_content="""
            Arthritis: Inflammation of one or more joints causing pain and stiffness.
            Common types include osteoarthritis (wear and tear) and rheumatoid arthritis (autoimmune).
            Symptoms include joint pain, swelling, decreased range of motion, and morning stiffness.
            Treatment includes pain relievers, anti-inflammatory drugs, physical therapy, and sometimes surgery.
            """,
            metadata={"source": "medlineplus", "topic": "Arthritis", "category": "Musculoskeletal"}
        ),
        Document(
            page_content="""
            Depression: A mental health disorder causing persistent sadness and loss of interest.
            Symptoms include low mood, loss of energy, changes in sleep and appetite, difficulty concentrating.
            Can be caused by genetic factors, brain chemistry, trauma, or major life changes.
            Treatment includes psychotherapy (talk therapy), medications (antidepressants), and lifestyle changes.
            """,
            metadata={"source": "medlineplus", "topic": "Depression", "category": "Mental Health"}
        ),
        Document(
            page_content="""
            Allergies: Immune system reactions to normally harmless substances (allergens).
            Common allergens include pollen, dust mites, pet dander, foods, and insect stings.
            Symptoms include sneezing, itching, runny nose, watery eyes, and skin rashes.
            Treatment includes avoiding triggers, antihistamines, nasal sprays, and immunotherapy.
            """,
            metadata={"source": "medlineplus", "topic": "Allergies", "category": "Immune System"}
        ),
        # Medicine Information
        Document(
            page_content="""
            Drug: Paracetamol (Panadol, Tylenol, Acetaminophen)
            Type: Pain reliever and fever reducer
            
            Uses: Treatment of mild to moderate pain (headaches, muscle aches, arthritis, backache, toothaches), 
            reduction of fever, relief of cold and flu symptoms.
            
            Dosage: Adults: 500-1000mg every 4-6 hours, maximum 4000mg per day.
            
            Side Effects: Rare at recommended doses. May cause nausea, vomiting, allergic reactions (rash, itching), 
            liver damage with overdose or chronic excessive use.
            
            Alternatives: Ibuprofen, Aspirin, Naproxen
            
            Warnings: Do not exceed recommended dose. Avoid alcohol consumption. Use with caution in liver disease.
            """,
            metadata={"source": "drugbank", "topic": "Paracetamol", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Ibuprofen (Advil, Motrin, Brufen)
            Type: Nonsteroidal anti-inflammatory drug (NSAID)
            
            Uses: Pain relief (headache, dental pain, menstrual cramps, muscle aches), reduction of inflammation 
            (arthritis, sports injuries), fever reduction.
            
            Dosage: Adults: 200-400mg every 4-6 hours, maximum 1200mg per day (OTC), up to 3200mg (prescription).
            
            Side Effects: Stomach upset, nausea, heartburn, indigestion, dizziness, drowsiness. 
            Risk of stomach ulcers with prolonged use. Increased risk of heart attack or stroke with high doses.
            
            Alternatives: Paracetamol, Naproxen, Aspirin, Celecoxib
            
            Warnings: Take with food. Avoid if you have stomach ulcers or bleeding disorders. 
            Use with caution in heart disease, high blood pressure, kidney disease.
            """,
            metadata={"source": "drugbank", "topic": "Ibuprofen", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Aspirin (Acetylsalicylic Acid)
            Type: NSAID with antiplatelet properties
            
            Uses: Pain relief, fever reduction, anti-inflammatory, prevention of heart attacks and strokes 
            (low-dose aspirin therapy).
            
            Dosage: Pain/fever: 300-600mg every 4-6 hours. Cardioprotection: 75-100mg daily.
            
            Side Effects: Stomach irritation, heartburn, nausea, increased bleeding risk, allergic reactions.
            
            Alternatives: Ibuprofen, Paracetamol, Naproxen, Clopidogrel (for blood thinning)
            
            Warnings: Do not give to children under 16 with fever (risk of Reye's syndrome). 
            Avoid before surgery. Use with caution in bleeding disorders, asthma, stomach ulcers.
            """,
            metadata={"source": "drugbank", "topic": "Aspirin", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Amoxicillin
            Type: Penicillin-type antibiotic
            
            Uses: Bacterial infections of ear, nose, throat, respiratory tract, urinary tract, skin. 
            H. pylori infection treatment.
            
            Dosage: 250-500mg every 8 hours or 500-875mg every 12 hours (varies by condition).
            
            Side Effects: Diarrhea, nausea, vomiting, rash, yeast infections, allergic reactions.
            
            Alternatives: Azithromycin, Cephalexin, Doxycycline, Trimethoprim-sulfamethoxazole
            
            Warnings: Complete full course even if feeling better. Do not use if allergic to penicillin. 
            May reduce effectiveness of birth control pills.
            """,
            metadata={"source": "drugbank", "topic": "Amoxicillin", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Omeprazole (Prilosec)
            Type: Proton pump inhibitor (PPI)
            
            Uses: Treatment of GERD (gastroesophageal reflux disease), heartburn, stomach and duodenal ulcers.
            
            Dosage: 20-40mg once daily, taken before meals.
            
            Side Effects: Headache, stomach pain, nausea, diarrhea, gas, constipation. 
            Long-term use: increased risk of bone fractures, vitamin B12 deficiency.
            
            Alternatives: Esomeprazole (Nexium), Lansoprazole, Pantoprazole, H2 blockers (Ranitidine, Famotidine)
            
            Warnings: May take 1-4 days for full effect. Not for immediate heartburn relief. 
            Long-term use associated with increased infection risk.
            """,
            metadata={"source": "drugbank", "topic": "Omeprazole", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Metformin (Glucophage)
            Type: Oral diabetes medication (biguanide)
            
            Uses: Type 2 diabetes management, PCOS treatment, prediabetes prevention.
            
            Dosage: Starting 500mg twice daily, may increase to 2000-2500mg daily.
            
            Side Effects: Diarrhea, nausea, stomach upset (especially when starting), metallic taste, 
            vitamin B12 deficiency (long-term), lactic acidosis (rare but serious).
            
            Alternatives: Sulfonylureas, DPP-4 inhibitors, GLP-1 agonists, SGLT2 inhibitors, Insulin
            
            Warnings: Take with meals. Monitor kidney function regularly. Temporarily discontinue before 
            surgery or imaging with contrast dye.
            """,
            metadata={"source": "drugbank", "topic": "Metformin", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Lisinopril
            Type: ACE inhibitor
            
            Uses: High blood pressure (hypertension), heart failure, post-heart attack treatment, diabetic kidney disease.
            
            Dosage: 10-40mg once daily.
            
            Side Effects: Persistent dry cough, dizziness, lightheadedness, headache, fatigue, 
            low blood pressure, elevated potassium levels.
            
            Alternatives: Losartan (ARB), Amlodipine (calcium channel blocker), Hydrochlorothiazide (diuretic)
            
            Warnings: Do not use during pregnancy. May cause severe allergic reactions. 
            Monitor blood pressure and potassium levels. Rise slowly to prevent dizziness.
            """,
            metadata={"source": "drugbank", "topic": "Lisinopril", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Atorvastatin (Lipitor)
            Type: Statin (HMG-CoA reductase inhibitor)
            
            Uses: High cholesterol, prevention of heart disease and stroke, familial hypercholesterolemia.
            
            Dosage: 10-80mg once daily.
            
            Side Effects: Muscle pain and weakness, liver enzyme elevation, digestive problems, 
            headache, increased blood sugar.
            
            Alternatives: Rosuvastatin (Crestor), Simvastatin, Pravastatin, Ezetimibe
            
            Warnings: Report unexplained muscle pain immediately. Avoid grapefruit juice. 
            Monitor liver function tests. Use effective contraception.
            """,
            metadata={"source": "drugbank", "topic": "Atorvastatin", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Albuterol (Salbutamol, Ventolin)
            Type: Bronchodilator (beta-2 agonist)
            
            Uses: Asthma rescue inhaler, exercise-induced bronchospasm, COPD.
            
            Dosage: 1-2 puffs every 4-6 hours as needed, or 15-30 minutes before exercise.
            
            Side Effects: Nervousness, tremor, rapid heartbeat, headache, dizziness, throat irritation.
            
            Alternatives: Levalbuterol, Ipratropium, Long-acting: Salmeterol, Formoterol
            
            Warnings: Use spacer device. Rinse mouth after use. If needing more than recommended doses, 
            contact doctor as it may indicate worsening asthma.
            """,
            metadata={"source": "drugbank", "topic": "Albuterol", "category": "Medicine", "type": "medicine"}
        ),
        Document(
            page_content="""
            Drug: Cetirizine (Zyrtec)
            Type: Second-generation antihistamine
            
            Uses: Seasonal allergies (hay fever), year-round allergies, hives (urticaria), itching.
            
            Dosage: 10mg once daily.
            
            Side Effects: Drowsiness (less than first-generation antihistamines), dry mouth, fatigue, headache.
            
            Alternatives: Loratadine (Claritin), Fexofenadine (Allegra), Diphenhydramine (Benadryl), 
            Nasal corticosteroids
            
            Warnings: May cause drowsiness. Avoid driving until effects are known. Avoid alcohol. 
            Use lower dose in kidney disease.
            """,
            metadata={"source": "drugbank", "topic": "Cetirizine", "category": "Medicine", "type": "medicine"}
        ),
    ]
    
    return sample_docs


def load_medical_documents() -> List:
    """Load medical documents from data directory or create samples"""
    print("📚 Loading medical documents...")
    
    try:
        # Try to load from data directory
        from app.rag.loader import load_all_medical_data
        docs = load_all_medical_data()
        
        if docs and len(docs) > 0:
            print(f"✅ Loaded {len(docs)} documents from data directory")
            return docs
    except Exception as e:
        print(f"⚠️  Could not load from data directory: {e}")
    
    # Use sample data if no real data available
    print("📝 Using sample medical data...")
    docs = create_sample_medical_data()
    print(f"✅ Created {len(docs)} sample documents")
    return docs


def create_embeddings_and_store(documents: List, force_recreate: bool = False):
    """Create embeddings and store in ChromaDB"""
    print("\n🔧 Setting up embeddings model...")
    
    try:
        from langchain_community.embeddings import SentenceTransformerEmbeddings
        from langchain_community.vectorstores import Chroma
    except ImportError:
        print("❌ Required packages not installed")
        print("   Run: pip install langchain-community sentence-transformers chromadb")
        return False
    
    # Create embeddings model
    embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")  # Smaller, faster model
    print(f"📊 Using embedding model: {embedding_model_name}")
    
    embeddings = SentenceTransformerEmbeddings(model_name=embedding_model_name)
    
    # Set up ChromaDB
    chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
    print(f"\n💾 ChromaDB directory: {chroma_dir}")
    
    # Remove existing database if force recreate
    if force_recreate and os.path.exists(chroma_dir):
        import shutil
        print("🗑️  Removing existing database...")
        shutil.rmtree(chroma_dir)
    
    # Create or load vector store
    print("🔄 Creating embeddings and storing in ChromaDB...")
    try:
        vectordb = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=chroma_dir
        )
        
        # Persist the database
        vectordb.persist()
        
        print(f"\n✅ Successfully embedded and stored {len(documents)} documents!")
        print(f"📁 Database saved to: {chroma_dir}")
        
        # Test retrieval
        print("\n🧪 Testing retrieval...")
        test_query = "What are the symptoms of diabetes?"
        results = vectordb.similarity_search(test_query, k=2)
        
        print(f"   Query: '{test_query}'")
        print(f"   Retrieved {len(results)} relevant documents")
        if results:
            print(f"   Top result: {results[0].metadata.get('topic', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating vector store: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MedChat Data Embedder")
    parser.add_argument("--recreate", action="store_true", help="Force recreate the vector database")
    parser.add_argument("--sample", action="store_true", help="Use sample data only")
    args = parser.parse_args()
    
    print("=" * 70)
    print("🏥 MedChat Medical Data Embedder")
    print("=" * 70)
    
    # Load documents
    documents = load_medical_documents()
    
    if not documents:
        print("❌ No documents to process")
        return 1
    
    # Create embeddings and store
    success = create_embeddings_and_store(documents, force_recreate=args.recreate)
    
    if success:
        print("\n" + "=" * 70)
        print("✅ Data processing complete!")
        print("=" * 70)
        print("\n📝 Next steps:")
        print("   1. Update your GEMINI_API_KEY in .env file")
        print("   2. Run the server: python run.py")
        print("   3. Test the API: python test_api.py")
        print("   4. Visit: http://localhost:8000/docs")
        return 0
    else:
        print("\n❌ Data processing failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
