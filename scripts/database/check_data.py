"""
Check Data Files Status
Shows which real medical data files are available
"""

from pathlib import Path

def check_data_status():
    """Check status of MedlinePlus and DrugBank data files"""
    
    print("\n" + "="*70)
    print("📊 MEDCHAT REAL DATA STATUS CHECK")
    print("="*70 + "\n")
    
    data_dir = Path("app/data/downloads")
    
    # Check MedlinePlus
    medlineplus_file = data_dir / "medlineplus.xml"
    
    print("1️⃣  MedlinePlus Health Topics:")
    print("   " + "-"*60)
    if medlineplus_file.exists():
        size_mb = medlineplus_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ FOUND: {medlineplus_file}")
        print(f"   📦 Size: {size_mb:.2f} MB")
        print("   📄 Status: Ready to load!")
    else:
        print(f"   ❌ NOT FOUND: {medlineplus_file}")
        print("   📥 Download from: https://medlineplus.gov/xml.html")
        print("   💡 Save as: app/data/downloads/medlineplus.xml")
    
    # Check DrugBank
    print("\n2️⃣  DrugBank Medicines:")
    print("   " + "-"*60)
    drugbank_file = data_dir / "drugbank" / "full database.xml"
    
    if drugbank_file.exists():
        size_mb = drugbank_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ FOUND: {drugbank_file}")
        print(f"   📦 Size: {size_mb:.2f} MB")
        print("   📄 Status: Ready to load!")
    else:
        print(f"   ❌ NOT FOUND: {drugbank_file}")
        print("   📥 Download from: https://go.drugbank.com/releases/latest")
        print("   💡 Save as: app/data/downloads/drugbank/full database.xml")
        print("   ⚠️  Requires FREE account signup")
    
    # Check ChromaDB
    print("\n3️⃣  ChromaDB Vector Database:")
    print("   " + "-"*60)
    chroma_dir = Path("chroma_db")
    
    if chroma_dir.exists():
        print(f"   ✅ EXISTS: {chroma_dir}")
        
        # Try to count documents
        try:
            db_file = chroma_dir / "chroma.sqlite3"
            if db_file.exists():
                size_mb = db_file.stat().st_size / (1024 * 1024)
                print(f"   📦 Database size: {size_mb:.2f} MB")
                
                if size_mb < 0.5:
                    print("   ⚠️  Database seems empty - run ingestion script")
                else:
                    print("   ✅ Database has data!")
        except:
            pass
    else:
        print(f"   ❌ NOT FOUND: {chroma_dir}")
        print("   💡 Will be created when you run: python ingest_all_data.py")
    
    # Summary
    print("\n" + "="*70)
    print("📋 SUMMARY & NEXT STEPS")
    print("="*70)
    
    has_medlineplus = medlineplus_file.exists()
    has_drugbank = drugbank_file.exists()
    has_chroma = chroma_dir.exists() and (chroma_dir / "chroma.sqlite3").exists()
    
    if has_medlineplus and has_drugbank:
        print("✅ Both datasets ready!")
        if not has_chroma:
            print("\n💡 Next step: Load data into ChromaDB")
            print("   Command: python ingest_all_data.py --clear")
        else:
            print("\n✅ Everything ready!")
            print("   Command: python run.py")
            
    elif has_medlineplus:
        print("✅ MedlinePlus ready!")
        print("❌ DrugBank missing (optional)")
        if not has_chroma:
            print("\n💡 Next step: Load MedlinePlus data")
            print("   Command: python ingest_all_data.py --medlineplus-only")
        else:
            print("\n✅ MedlinePlus data loaded!")
            print("   Command: python run.py")
            
    elif has_drugbank:
        print("❌ MedlinePlus missing (recommended)")
        print("✅ DrugBank ready!")
        print("\n💡 Download MedlinePlus first for best results")
        
    else:
        print("❌ No datasets found")
        print("\n📥 Download instructions:")
        print("   See: REAL_DATA_SETUP.md")
        print("   Or visit: https://medlineplus.gov/xml.html")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    check_data_status()
