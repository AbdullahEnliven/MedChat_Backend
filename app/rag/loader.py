"""
Loader for medical documents used by the embedder.

This provides a single function `load_all_medical_data()` which attempts to
load formatted documents from the data ingestion modules (`app.data`).
If no downloaded data is present it returns an empty list so the embedder
can fall back to sample documents.
"""
from pathlib import Path
from typing import List, Dict
import json


def _load_medlineplus_documents() -> List[Dict]:
    """Load formatted MedlinePlus documents if available."""
    try:
        from app.data.ingest_medlineplus import DATA_DIR, format_for_embeddings
    except Exception:
        return []

    xml_json = DATA_DIR / "medlineplus_topics.json"
    if not xml_json.exists():
        return []

    try:
        with open(xml_json, 'r', encoding='utf-8') as f:
            topics = json.load(f)
    except Exception:
        return []

    # Convert parsed topics to the same shape expected by the embedder
    docs = format_for_embeddings(topics)
    # `format_for_embeddings` returns list[dict] with keys 'content' and 'metadata'
    # Convert to langchain Document style if needed lazily in embedder
    return docs


def _load_drugbank_documents() -> List[Dict]:
    """Load DrugBank formatted documents if available (optional)."""
    try:
        from app.data.ingest_drugbank import DATA_DIR as DB_DATA_DIR, format_for_embeddings as db_format
    except Exception:
        return []

    json_path = DB_DATA_DIR / "drugbank_drugs.json"
    if not json_path.exists():
        return []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            drugs = json.load(f)
    except Exception:
        return []

    docs = db_format(drugs)
    return docs


def load_all_medical_data() -> List[Dict]:
    """Aggregate all available medical documents for embedding.

    Returns a list of document dicts with keys `content` and `metadata`.
    The embedder will accept these or fall back to sample data.
    """
    docs = []

    # MedlinePlus first
    try:
        mpl_docs = _load_medlineplus_documents()
        if mpl_docs:
            docs.extend(mpl_docs)
    except Exception:
        pass

    # DrugBank next
    try:
        db_docs = _load_drugbank_documents()
        if db_docs:
            docs.extend(db_docs)
    except Exception:
        pass

    return docs
