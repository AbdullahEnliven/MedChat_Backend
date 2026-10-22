"""
DrugBank Data Ingestion Script
Processes DrugBank Open Data XML for drug information
Source: https://go.drugbank.com/releases/latest

NOTE: Requires manual download (free account needed)
License: CC BY-NC 4.0 (Non-commercial use only)
"""

import os
import xml.etree.ElementTree as ET
from typing import List, Dict
from pathlib import Path
import zipfile

DATA_DIR = Path(__file__).parent / "downloads"
DRUGBANK_NS = {'db': 'http://www.drugbank.ca'}


def extract_drugbank_zip(zip_path: Path) -> Path:
    """Extract DrugBank XML from downloaded zip file"""
    print(f"📦 Extracting {zip_path}...")
    
    extract_dir = DATA_DIR / "drugbank"
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    # Find the XML file
    xml_files = list(extract_dir.glob("*.xml"))
    if not xml_files:
        raise FileNotFoundError(f"No XML file found in {extract_dir}")
    
    xml_path = xml_files[0]
    print(f"✅ Extracted to {xml_path}")
    return xml_path


def parse_drugbank_xml(xml_path: Path, limit: int = None) -> List[Dict]:
    """
    Parse DrugBank XML and extract drug information
    
    Args:
        xml_path: Path to DrugBank XML file
        limit: Maximum number of drugs to parse (for testing)
        
    Returns:
        List of drug dictionaries
    """
    print(f"📖 Parsing DrugBank XML from {xml_path}...")
    print("⏳ This may take a few minutes (large file)...")
    
    drugs = []
    
    try:
        # Parse iteratively to handle large files
        context = ET.iterparse(xml_path, events=('end',))
        
        count = 0
        for event, elem in context:
            # DrugBank XML uses <record> tags, not <drug>
            if elem.tag == 'record':
                drug = {}
                
                # Basic info (no namespace in this XML format)
                drug['drugbank_id'] = elem.findtext('drugbank-id', default='')
                drug['name'] = elem.findtext('name', default='')
                drug['type'] = elem.findtext('type', default='small molecule')
                
                # Description
                drug['description'] = elem.findtext('description', default='')
                
                # Indication (what it's used for)
                drug['indication'] = elem.findtext('indication', default='')
                
                # Pharmacodynamics (how it works)
                drug['pharmacodynamics'] = elem.findtext('pharmacodynamics', default='')
                
                # Mechanism of action
                drug['mechanism_of_action'] = elem.findtext('mechanism-of-action', default='')
                
                # Toxicity
                drug['toxicity'] = elem.findtext('toxicity', default='')
                
                # Categories
                categories_elem = elem.find('categories')
                if categories_elem is not None:
                    categories = [cat.findtext('category', default='') 
                                  for cat in categories_elem.findall('category')]
                    drug['categories'] = [c for c in categories if c]
                else:
                    drug['categories'] = []
                
                # Synonyms
                synonyms_elem = elem.find('synonyms')
                if synonyms_elem is not None:
                    synonyms = [syn.text for syn in synonyms_elem.findall('synonym') if syn.text]
                    drug['synonyms'] = synonyms[:5]  # Limit to 5
                else:
                    drug['synonyms'] = []
                
                # Only add if we have meaningful content
                if drug['name'] and (drug['description'] or drug['indication']):
                    drugs.append(drug)
                    count += 1
                
                # Clear element to save memory
                elem.clear()
                
                if limit and count >= limit:
                    print(f"⚠️ Reached limit of {limit} drugs")
                    break
                
                if count % 100 == 0:
                    print(f"   Processed {count} drugs...")
        
        print(f"✅ Parsed {len(drugs)} drugs")
        return drugs
        
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        raise


def format_for_embeddings(drugs: List[Dict]) -> List[Dict]:
    """
    Format DrugBank data for ChromaDB embeddings
    
    Args:
        drugs: List of parsed drugs
        
    Returns:
        List of formatted documents
    """
    print("🔄 Formatting drugs for embeddings...")
    
    documents = []
    
    for drug in drugs:
        # Create comprehensive text for embedding
        synonyms_text = ', '.join(drug['synonyms']) if drug['synonyms'] else 'None'
        categories_text = ', '.join(drug['categories']) if drug['categories'] else 'None'
        
        content = f"""
Drug Name: {drug['name']}
Also Known As: {synonyms_text}
Type: {drug['type']}

Description:
{drug['description']}

Indications (Uses):
{drug['indication']}

How It Works (Mechanism of Action):
{drug['mechanism_of_action']}

Pharmacodynamics:
{drug['pharmacodynamics']}

Side Effects and Toxicity:
{drug['toxicity']}

Categories: {categories_text}
        """.strip()
        
        doc = {
            'content': content,
            'metadata': {
                'source': 'DrugBank',
                'drugbank_id': drug['drugbank_id'],
                'drug_name': drug['name'],
                'type': drug['type'],
                'categories': categories_text
            }
        }
        
        documents.append(doc)
    
    print(f"✅ Formatted {len(documents)} documents")
    return documents


def save_to_json(drugs: List[Dict], output_path: Path):
    """Save parsed drugs to JSON for inspection"""
    import json
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(drugs, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved drugs to {output_path}")


def main():
    """Main ingestion workflow"""
    print("=" * 60)
    print("💊 DrugBank Data Ingestion")
    print("=" * 60)
    
    # Check for XML file
    xml_path = DATA_DIR / "drugbank" / "full database.xml"
    zip_path = DATA_DIR / "drugbank.xml.zip"
    
    if not xml_path.exists():
        if zip_path.exists():
            print(f"📦 Found zip file: {zip_path}")
            xml_path = extract_drugbank_zip(zip_path)
        else:
            print("\n❌ DrugBank XML file not found!")
            print("\n📥 Manual download required:")
            print("1. Visit https://go.drugbank.com/releases/latest")
            print("2. Create free account (if needed)")
            print("3. Download 'DrugBank Open Data' XML")
            print(f"4. Place ZIP or XML in: {DATA_DIR}/")
            print("   Expected filename: drugbank.xml.zip or full database.xml")
            print("\n⚖️ License: CC BY-NC 4.0 (Non-commercial use only)")
            return
    
    # Parse XML (limit for testing)
    print("\n💡 Parsing first 500 drugs (set limit=None for all)")
    drugs = parse_drugbank_xml(xml_path, limit=500)
    
    # Format for embeddings
    documents = format_for_embeddings(drugs)
    
    # Save to JSON
    json_path = DATA_DIR / "drugbank_data.json"
    save_to_json(drugs, json_path)
    
    print("\n" + "=" * 60)
    print("✅ DrugBank data ingestion complete!")
    print(f"📊 Total drugs: {len(drugs)}")
    print(f"📁 JSON saved to: {json_path}")
    print("\n💡 Next step: Run the embedder to load into ChromaDB")
    print("   python -m app.data.load_into_chromadb")
    print("=" * 60)
    
    return documents


if __name__ == "__main__":
    main()
