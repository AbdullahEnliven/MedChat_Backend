"""
MedlinePlus Data Ingestion Script
Downloads and processes MedlinePlus health topics XML feed
Source: https://medlineplus.gov/xml.html
"""

import os
import xml.etree.ElementTree as ET
import requests
from typing import List, Dict
from pathlib import Path
import zipfile
import shutil

# MedlinePlus provides XML at this URL - check https://medlineplus.gov/xml.html for latest
MEDLINEPLUS_URL = "https://medlineplus.gov/xml.html"  # Will redirect to latest XML
DATA_DIR = Path(__file__).parent / "downloads"
EXTRACTED_DIR = DATA_DIR / "medlineplus"


def download_medlineplus_data(force_download: bool = False) -> Path:
    """
    Download MedlinePlus XML data
    
    Args:
        force_download: Download even if file exists
        
    Returns:
        Path to downloaded XML file
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    xml_path = DATA_DIR / "medlineplus.xml"
    
    if xml_path.exists() and not force_download:
        print(f"✅ MedlinePlus data already exists at {xml_path}")
        return xml_path
    
    # Try to download the XML directly
    print(f"📥 Downloading MedlinePlus XML data...")
    print("   Source: https://medlineplus.gov/xml.html")
    
    # The actual XML file URL (check https://medlineplus.gov/xml.html for latest)
    xml_urls = [
        "https://medlineplus.gov/xml/mplus_topics.xml",  # Generic latest
        "https://medlineplus.gov/xml/mplus_topics_2024-10-23.xml",
        "https://medlineplus.gov/xml/mplus_topics_2024-09-25.xml",
    ]
    
    for url in xml_urls:
        try:
            print(f"   Trying: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Save XML
            with open(xml_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ Downloaded successfully to {xml_path}")
            return xml_path
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            continue
    
    # If all downloads failed
    print("\n❌ All download attempts failed!")
    print("\n📥 MANUAL DOWNLOAD REQUIRED:")
    print("=" * 70)
    print("1. Visit: https://medlineplus.gov/xml.html")
    print("2. Find the latest 'mplus_topics_*.xml' file")
    print("3. Download it")
    print(f"4. Save as: {xml_path}")
    print("=" * 70)
    raise Exception("Could not download MedlinePlus data")


def parse_medlineplus_xml(xml_path: Path) -> List[Dict]:
    """
    Parse MedlinePlus XML and extract health topics
    
    Args:
        xml_path: Path to XML file
        
    Returns:
        List of health topic dictionaries
    """
    print(f"📖 Parsing MedlinePlus XML from {xml_path}...")
    
    topics = []
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # MedlinePlus uses health-topic elements
        for record in root.findall(".//health-topic"):
            topic = {}
            
            # Extract key fields
            topic['id'] = record.get('id', '')
            topic['title'] = record.get('title', '')
            topic['url'] = record.get('url', '')
            topic['language'] = record.get('language', 'English')
            topic['date-created'] = record.get('date-created', '')
            topic['meta-desc'] = record.get('meta-desc', '')
            
            # Extract full summary
            full_summary = record.find('full-summary')
            if full_summary is not None:
                topic['summary'] = full_summary.text or ''
            else:
                topic['summary'] = topic['meta-desc']
            
            # Extract also-called (synonyms)
            also_called = record.find('also-called')
            if also_called is not None:
                topic['also_called'] = also_called.text or ''
            else:
                topic['also_called'] = ''
            
            # Extract related topics
            see_reference = record.find('see-reference')
            if see_reference is not None:
                topic['related'] = see_reference.get('title', '')
            else:
                topic['related'] = ''
            
            # Extract groups (categories)
            groups = record.findall('.//group')
            topic['categories'] = [g.get('id', '') for g in groups if g.get('id')]
            
            # Only add if we have meaningful content
            if topic['title'] and topic['summary']:
                topics.append(topic)
        
        print(f"✅ Parsed {len(topics)} health topics")
        return topics
        
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        raise


def format_for_embeddings(topics: List[Dict]) -> List[Dict]:
    """
    Format MedlinePlus topics for ChromaDB embeddings
    
    Args:
        topics: List of parsed topics
        
    Returns:
        List of formatted documents
    """
    print("🔄 Formatting topics for embeddings...")
    
    documents = []
    
    for topic in topics:
        # Create comprehensive text for embedding
        content = f"""
Title: {topic['title']}
Also Known As: {topic['also_called']}

Summary:
{topic['summary']}

Categories: {', '.join(topic['categories'])}
Related Topics: {topic['related']}
        """.strip()
        
        doc = {
            'content': content,
            'metadata': {
                'source': 'MedlinePlus',
                'source_url': topic['url'],
                'title': topic['title'],
                'topic_id': topic['id'],
                'categories': ', '.join(topic['categories']),
                'date_created': topic['date-created']
            }
        }
        
        documents.append(doc)
    
    print(f"✅ Formatted {len(documents)} documents")
    return documents


def save_to_json(topics: List[Dict], output_path: Path):
    """Save parsed topics to JSON for inspection"""
    import json
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved topics to {output_path}")


def main():
    """Main ingestion workflow"""
    print("=" * 60)
    print("🏥 MedlinePlus Data Ingestion")
    print("=" * 60)
    
    # Step 1: Download data
    try:
        xml_path = download_medlineplus_data(force_download=False)
    except Exception:
        print("\n💡 Manual download instructions:")
        print("1. Visit https://medlineplus.gov/xml.html")
        print("2. Download 'mplus_topics_*.xml'")
        print("3. Place in: app/data/downloads/medlineplus.xml")
        return
    
    # Step 2: Parse XML
    topics = parse_medlineplus_xml(xml_path)
    
    # Step 3: Format for embeddings
    documents = format_for_embeddings(topics)
    
    # Step 4: Save to JSON (optional)
    json_path = DATA_DIR / "medlineplus_topics.json"
    save_to_json(topics, json_path)
    
    print("\n" + "=" * 60)
    print("✅ MedlinePlus data ingestion complete!")
    print(f"📊 Total topics: {len(topics)}")
    print(f"📁 JSON saved to: {json_path}")
    print("\n💡 Next step: Run the embedder to load into ChromaDB")
    print("   python -m app.data.load_into_chromadb")
    print("=" * 60)
    
    return documents


if __name__ == "__main__":
    main()
