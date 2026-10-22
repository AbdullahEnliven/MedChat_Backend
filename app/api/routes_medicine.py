"""
Medicine Scanner - Drug Information Lookup
Route: GET /medicine/{name}
Route: POST /medicine/scan (Camera Upload)
Purpose: User enters medicine name or uploads photo → show usage, side effects, alternatives
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
import io
from datetime import datetime
from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.chat import SearchHistory
try:
    from app.rag.retriever import get_retriever
    from app.core.config import settings
    from app.utils.ocr import extract_medicine_names_from_image, extract_text_from_image, validate_tesseract_installation
    import google.generativeai as genai
    import json
    import re
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
router = APIRouter(prefix="/api/v1/medicine", tags=["Medicine Info"])
class MedicineInfo(BaseModel):
    medicine_name: str
    description: str
    usage: str
    dosage: Optional[str] = None
    side_effects: str
    alternatives: str
    warnings: str
    source: str
class CameraScanRequest(BaseModel):
    detected_text: str
    medicine_name: str
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    dosage: Optional[str] = None
    manufacturer: Optional[str] = None
    confidence: str
    source: str
    sources: List[str] = []
    metadata: dict = {}
    medicine_info: Optional[MedicineInfo] = None
class MedicineSearchResult(BaseModel):
    query: str
    results: List[dict]
    total_found: int
@router.post("/scan", response_model=CameraScanRequest)
async def scan_medicine_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Smart Medicine Scanner - RAG-First with AI Fallback
    Priority order:
    1. Try OCR (Tesseract) to extract text from image
    2. If OCR fails or unclear, use Vision AI (Gemini) to identify medicine
    3. Search RAG database first (primary source)
    4. If not in RAG, fallback to AI knowledge (last resort)
    5. Return clean, highlighted response (no JSON metadata to user)
    Args:
        file: Image file uploaded from camera (JPEG, PNG)
        current_user: Authenticated user (required)
        db: Database session
    Returns:
        Clean medicine information with clear sections
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available. Install required packages."
        )
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image (JPEG, PNG)"
        )
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        extracted_text = ""
        brand_name = ""
        generic_name = ""
        dosage = ""
        manufacturer = ""
        confidence = "medium"
        ocr_quality = "fair"
        use_vision_fallback = True
        try:
            if validate_tesseract_installation():
                extracted_text = extract_text_from_image(image_bytes)
                if extracted_text and len(extracted_text.strip()) > 10:
                    api_keys = [
                        settings.GEMINI_API_KEY,
                        getattr(settings, 'GEMINI_API_KEY_BACKUP', ''),
                        getattr(settings, 'GEMINI_API_KEY_BACKUP2', '')
                    ]
                    api_keys = [key for key in api_keys if key]
                    model = None
                    for i, api_key in enumerate(api_keys):
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-2.0-flash-exp')
                            break
                        except:
                            continue
                    ocr_prompt = f"""Analyze this text from a medicine package. Extract ONLY the medicine information.
Text: {extracted_text}
Identify:
1. Brand name (prominent/bold text)
2. Generic name (scientific name)
3. Dosage (mg/ml amount)
4. Manufacturer
Return JSON:
{{"brand_name": "...", "generic_name": "...", "dosage": "...", "manufacturer": "...", "confidence": "high/medium/low"}}"""
                    try:
                        ocr_response = model.generate_content(ocr_prompt)
                        ocr_text = ocr_response.text.strip()
                    except Exception as e:
                        if "429" in str(e) or "Resource exhausted" in str(e):
                            for i, api_key in enumerate(api_keys[1:], 1):
                                try:
                                    genai.configure(api_key=api_key)
                                    model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                    ocr_response = model.generate_content(ocr_prompt)
                                    ocr_text = ocr_response.text.strip()
                                    break
                                except Exception as backup_error:
                                    if i == len(api_keys) - 1:
                                        raise backup_error
                                    continue
                        else:
                            raise
                    import re
                    if "```json" in ocr_text:
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', ocr_text, re.DOTALL)
                        if json_match:
                            ocr_text = json_match.group(1)
                    ocr_data = json.loads(ocr_text)
                    brand_name = ocr_data.get("brand_name", "").strip()
                    generic_name = ocr_data.get("generic_name", "").strip()
                    dosage = ocr_data.get("dosage", "").strip()
                    manufacturer = ocr_data.get("manufacturer", "").strip()
                    confidence = ocr_data.get("confidence", "medium")
                    if brand_name and brand_name.upper() not in ["UNKNOWN", "N/A", ""]:
                        ocr_quality = "good"
                        use_vision_fallback = False
                    else:
                        use_vision_fallback = True
                else:
                    use_vision_fallback = True
            else:
                use_vision_fallback = True
        except Exception as e:
            use_vision_fallback = True
        if use_vision_fallback:
            import io
            from PIL import Image
            api_keys = [
                settings.GEMINI_API_KEY,
                getattr(settings, 'GEMINI_API_KEY_BACKUP', ''),
                getattr(settings, 'GEMINI_API_KEY_BACKUP2', '')
            ]
            api_keys = [key for key in api_keys if key]
            vision_model = None
            for i, api_key in enumerate(api_keys):
                try:
                    genai.configure(api_key=api_key)
                    vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    break
                except:
                    continue
            image = Image.open(io.BytesIO(image_bytes))
            vision_prompt = """Analyze this medicine package image.
Identify:
1. Brand Name (LARGEST/BOLDEST text)
2. Generic Name (scientific/chemical name)
3. Dosage (mg/ml)
4. Manufacturer
Common medicines:
- Glucophage = Metformin (diabetes)
- Panadol = Paracetamol (pain/fever)
- Disprin = Aspirin
- Augmentin = Amoxicillin
Return JSON (no markdown):
{"brand_name": "...", "generic_name": "...", "dosage": "...", "manufacturer": "...", "confidence": "high/medium/low"}"""
            try:
                vision_response = vision_model.generate_content([vision_prompt, image])
                vision_text = vision_response.text.strip()
            except Exception as vision_error:
                if "429" in str(vision_error) or "Resource exhausted" in str(vision_error):
                    for i, api_key in enumerate(api_keys[1:], 1):
                        try:
                            genai.configure(api_key=api_key)
                            vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
                            vision_response = vision_model.generate_content([vision_prompt, image])
                            vision_text = vision_response.text.strip()
                            break
                        except Exception as backup_error:
                            if i == len(api_keys) - 1:
                                raise vision_error
                            continue
                else:
                    raise
            try:
                if "```json" in vision_text:
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', vision_text, re.DOTALL)
                    if json_match:
                        vision_text = json_match.group(1)
                vision_data = json.loads(vision_text)
                brand_name = vision_data.get("brand_name", "").strip()
                generic_name = vision_data.get("generic_name", "").strip()
                dosage = vision_data.get("dosage", "").strip()
                manufacturer = vision_data.get("manufacturer", "").strip()
                confidence = vision_data.get("confidence", "medium")
                ocr_quality = "fair"
            except Exception as vision_error:
                if extracted_text and len(extracted_text.strip()) > 5:
                    lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
                    if lines:
                        brand_name = lines[0]
                        generic_name = lines[1] if len(lines) > 1 else ""
                        dosage = ""
                        manufacturer = ""
                        confidence = "low"
                        ocr_quality = "poor"
                        import re
                        dosage_match = re.search(r'(\d+\s*mg|\d+\s*ml)', extracted_text, re.IGNORECASE)
                        if dosage_match:
                            dosage = dosage_match.group(1)
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="Could not extract medicine information. API rate limit reached. Please try again later."
                        )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract text from image. Please ensure image is clear and contains visible text."
                    )
        if brand_name and brand_name.upper() not in ["UNKNOWN", "N/A", "", "NOT VISIBLE"]:
            medicine_name = brand_name
            if dosage and dosage.upper() not in ["UNKNOWN", "N/A", ""]:
                medicine_name = f"{brand_name} {dosage}"
        elif generic_name and generic_name.upper() not in ["UNKNOWN", "N/A", ""]:
            medicine_name = generic_name
            if dosage and dosage.upper() not in ["UNKNOWN", "N/A", ""]:
                medicine_name = f"{generic_name} {dosage}"
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not identify medicine from image. Please ensure text is clearly visible."
            )
        vectordb = get_retriever()
        search_queries = [
            f"{medicine_name}",
            f"{brand_name}" if brand_name else "",
            f"{generic_name}" if generic_name else ""
        ]
        search_query = " ".join([q for q in search_queries if q])
        docs = vectordb.similarity_search(search_query, k=3)
        medicine_in_rag = False
        if docs and len(docs) > 0:
            for doc in docs:
                content_lower = doc.page_content.lower()
                if (medicine_name.lower() in content_lower or 
                    (brand_name and brand_name.lower() in content_lower) or 
                    (generic_name and generic_name.lower() in content_lower)):
                    medicine_in_rag = True
                    break
        if medicine_in_rag:
            source = "database"
            confidence = "high"
        else:
            source = "ai_fallback"
            confidence = "medium"
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        try:
            user_context = ""
            if current_user.age:
                user_context += f"\n- Patient Age: {current_user.age} years"
            if current_user.gender:
                user_context += f"\n- Patient Gender: {current_user.gender}"
            if medicine_in_rag:
                context = "\n\n".join([doc.page_content for doc in docs[:3]])
                age_instruction = ""
                if current_user.age:
                    if current_user.age < 2:
                        age_instruction = "\n\n**CRITICAL: This is for an INFANT (under 2 years). Provide INFANT-SPECIFIC dosage, side effects, and warnings. Include weight-based dosing if applicable.**"
                    elif current_user.age < 12:
                        age_instruction = f"\n\n**CRITICAL: This is for a CHILD ({current_user.age} years old). Provide PEDIATRIC dosage, common side effects in children, and child-specific warnings.**"
                    elif current_user.age < 18:
                        age_instruction = f"\n\n**CRITICAL: This is for a TEENAGER ({current_user.age} years old). Provide ADOLESCENT dosage and age-appropriate warnings.**"
                    elif current_user.age >= 65:
                        age_instruction = f"\n\n**CRITICAL: This is for a SENIOR ({current_user.age} years old). Provide GERIATRIC dosage adjustments, elderly-specific side effects, and special precautions for older adults.**"
                    else:
                        age_instruction = f"\n\n**Note: This is for an ADULT ({current_user.age} years old). Provide standard adult dosage.**"
                prompt = f"""You are a medical information assistant. Based on the database information below, provide CLEAN and HIGHLIGHTED medicine details TAILORED TO THE PATIENT'S AGE.
DATABASE CONTEXT:
{context}
MEDICINE IDENTIFIED:
- Name: {medicine_name}
- Brand: {brand_name}
- Generic: {generic_name}
- Dosage: {dosage}
{user_context}{age_instruction}
IMPORTANT: Provide a CLEAN, USER-FRIENDLY response. NO JSON visible to user. Format as:
📋 **Description:**
[One clear paragraph about what this medicine is]
💊 **Usage & Dosage (Age-Specific):**
[What it treats, HOW TO TAKE IT FOR THIS AGE GROUP, EXACT DOSAGE FOR THIS AGE]
{"- INFANT dosage (if under 2): weight-based or age-based" if current_user.age and current_user.age < 2 else ""}
{"- PEDIATRIC dosage (child-safe amount)" if current_user.age and 2 <= current_user.age < 12 else ""}
{"- ADOLESCENT dosage" if current_user.age and 12 <= current_user.age < 18 else ""}
{"- ADULT dosage" if current_user.age and 18 <= current_user.age < 65 else ""}
{"- GERIATRIC dosage (elderly-adjusted)" if current_user.age and current_user.age >= 65 else ""}
- Frequency (how many times per day)
- Duration (how long to take)
- Administration (with food/water, etc.)
⚠️ **Side Effects (Age-Specific):**
{"• Common side effects IN INFANTS" if current_user.age and current_user.age < 2 else ""}
{"• Common side effects IN CHILDREN" if current_user.age and 2 <= current_user.age < 12 else ""}
{"• Common side effects IN TEENAGERS" if current_user.age and 12 <= current_user.age < 18 else ""}
{"• Common side effects IN ADULTS" if current_user.age and 18 <= current_user.age < 65 else ""}
{"• Common side effects IN ELDERLY" if current_user.age and current_user.age >= 65 else ""}
• [List 3-5 most common side effects for this age group]
• [Serious/emergency side effects specific to this age]
🔄 **Alternatives (Age-Appropriate):**
• [Alternative medicine 1 - safe for this age]
• [Alternative medicine 2 - safe for this age]
• [Alternative medicine 3 - safe for this age]
⛔ **Warnings & Precautions (Age-Specific):**
{"⚠️ INFANT WARNING: " if current_user.age and current_user.age < 2 else ""}
{"⚠️ PEDIATRIC WARNING: " if current_user.age and 2 <= current_user.age < 12 else ""}
{"⚠️ ADOLESCENT WARNING: " if current_user.age and 12 <= current_user.age < 18 else ""}
{"⚠️ ELDERLY WARNING: " if current_user.age and current_user.age >= 65 else ""}
[Critical warnings for this age group, contraindications, when to avoid]
Return ONLY plain text with these sections clearly formatted. Use bullet points (•) for lists."""
            else:
                age_instruction = ""
                if current_user.age:
                    if current_user.age < 2:
                        age_instruction = "\n\n**CRITICAL: This is for an INFANT (under 2 years). Provide INFANT-SPECIFIC dosage, side effects, and warnings. Include weight-based dosing if applicable.**"
                    elif current_user.age < 12:
                        age_instruction = f"\n\n**CRITICAL: This is for a CHILD ({current_user.age} years old). Provide PEDIATRIC dosage, common side effects in children, and child-specific warnings.**"
                    elif current_user.age < 18:
                        age_instruction = f"\n\n**CRITICAL: This is for a TEENAGER ({current_user.age} years old). Provide ADOLESCENT dosage and age-appropriate warnings.**"
                    elif current_user.age >= 65:
                        age_instruction = f"\n\n**CRITICAL: This is for a SENIOR ({current_user.age} years old). Provide GERIATRIC dosage adjustments, elderly-specific side effects, and special precautions for older adults.**"
                    else:
                        age_instruction = f"\n\n**Note: This is for an ADULT ({current_user.age} years old). Provide standard adult dosage.**"
                prompt = f"""You are a medical information assistant. Provide CLEAN and HIGHLIGHTED details about this medicine TAILORED TO THE PATIENT'S AGE.
MEDICINE IDENTIFIED:
- Name: {medicine_name}
- Brand: {brand_name}
- Generic: {generic_name}
- Dosage: {dosage}
- Manufacturer: {manufacturer}
{user_context}{age_instruction}
NOTE: This information is from AI knowledge as this medicine is not in our verified database. Recommend consulting a healthcare professional.
IMPORTANT: Provide a CLEAN, USER-FRIENDLY response. NO JSON visible to user. Format as:
📋 **Description:**
[One clear paragraph about what this medicine is]
💊 **Usage & Dosage (Age-Specific):**
[What it treats, HOW TO TAKE IT FOR THIS AGE GROUP, EXACT DOSAGE FOR THIS AGE]
{"- INFANT dosage (if under 2): weight-based or age-based" if current_user.age and current_user.age < 2 else ""}
{"- PEDIATRIC dosage (child-safe amount)" if current_user.age and 2 <= current_user.age < 12 else ""}
{"- ADOLESCENT dosage" if current_user.age and 12 <= current_user.age < 18 else ""}
{"- ADULT dosage" if current_user.age and 18 <= current_user.age < 65 else ""}
{"- GERIATRIC dosage (elderly-adjusted)" if current_user.age and current_user.age >= 65 else ""}
- Frequency (how many times per day)
- Duration (how long to take)
- Administration (with food/water, etc.)
⚠️ **Side Effects (Age-Specific):**
{"• Common side effects IN INFANTS" if current_user.age and current_user.age < 2 else ""}
{"• Common side effects IN CHILDREN" if current_user.age and 2 <= current_user.age < 12 else ""}
{"• Common side effects IN TEENAGERS" if current_user.age and 12 <= current_user.age < 18 else ""}
{"• Common side effects IN ADULTS" if current_user.age and 18 <= current_user.age < 65 else ""}
{"• Common side effects IN ELDERLY" if current_user.age and current_user.age >= 65 else ""}
• [List 3-5 most common side effects for this age group]
• [Serious/emergency side effects specific to this age]
🔄 **Alternatives (Age-Appropriate):**
• [Alternative medicine 1 - safe for this age]
• [Alternative medicine 2 - safe for this age]
• [Alternative medicine 3 - safe for this age]
⛔ **Warnings & Precautions (Age-Specific):**
{"⚠️ INFANT WARNING: " if current_user.age and current_user.age < 2 else ""}
{"⚠️ PEDIATRIC WARNING: " if current_user.age and 2 <= current_user.age < 12 else ""}
{"⚠️ ADOLESCENT WARNING: " if current_user.age and 12 <= current_user.age < 18 else ""}
{"⚠️ ELDERLY WARNING: " if current_user.age and current_user.age >= 65 else ""}
[Critical warnings for this age group, contraindications, when to avoid]
Return ONLY plain text with these sections clearly formatted. Use bullet points (•) for lists."""
            response = model.generate_content(prompt)
            clean_response = response.text.strip()
            description_match = re.search(r'📋\s*\*\*Description:\*\*\s*\n(.*?)(?=\n\n💊|\Z)', clean_response, re.DOTALL)
            usage_match = re.search(r'💊\s*\*\*Usage & Dosage \(Age-Specific\):\*\*\s*\n(.*?)(?=\n\n⚠️|\Z)', clean_response, re.DOTALL)
            side_effects_match = re.search(r'⚠️\s*\*\*Side Effects \(Age-Specific\):\*\*\s*\n(.*?)(?=\n\n🔄|\Z)', clean_response, re.DOTALL)
            alternatives_match = re.search(r'🔄\s*\*\*Alternatives \(Age-Appropriate\):\*\*\s*\n(.*?)(?=\n\n⛔|\Z)', clean_response, re.DOTALL)
            warnings_match = re.search(r'⛔\s*\*\*Warnings & Precautions \(Age-Specific\):\*\*\s*\n(.*?)(?=\Z)', clean_response, re.DOTALL)
            description = description_match.group(1).strip() if description_match else f"Information about {medicine_name}"
            usage = usage_match.group(1).strip() if usage_match else "Consult healthcare professional for usage"
            side_effects_text = side_effects_match.group(1).strip() if side_effects_match else "• Consult healthcare professional"
            alternatives_text = alternatives_match.group(1).strip() if alternatives_match else "• Consult healthcare professional"
            warnings = warnings_match.group(1).strip() if warnings_match else "Consult healthcare professional before use"
            medicine_info = MedicineInfo(
                medicine_name=medicine_name,
                description=description,
                usage=usage,
                dosage=dosage if dosage else None,
                side_effects=side_effects_text,  # String format with bullets
                alternatives=alternatives_text,  # String format with bullets
                warnings=warnings,
                source=source
            )
            try:
                import json
                search_entry = SearchHistory(
                    user_id=current_user.id,
                    search_query=f"Medicine Scan: {medicine_name}",
                    search_response=json.dumps({
                        "medicine_name": medicine_name,
                        "brand_name": brand_name,
                        "generic_name": generic_name,
                        "dosage": dosage,
                        "manufacturer": manufacturer,
                        "source": source,
                        "confidence": confidence,
                        "response": clean_response[:1000]  # Save first 1000 chars of clean response
                    }),
                    search_type="medicine",
                    results_count=1
                )
                db.add(search_entry)
                db.commit()
            except Exception as e:
                pass
            
            sources_list = []
            if medicine_in_rag and docs:
                for doc in docs:
                    doc_source = doc.metadata.get("source", "RAG Database")
                    if doc_source not in sources_list:
                        sources_list.append(doc_source)
            else:
                sources_list = ["ai_knowledge"]
            api_key_used = "primary"
            if hasattr(genai, '_current_api_key_index'):
                api_key_used = f"backup{genai._current_api_key_index}" if genai._current_api_key_index > 0 else "primary"
            response_metadata = {
                "ocr_quality": ocr_quality if 'ocr_quality' in locals() else "good",
                "detection_method": "vision_ai" if 'vision_response' in locals() else "ocr_text",
                "confidence_level": confidence,
                "rag_documents_found": len(docs) if docs else 0,
                "medicine_in_database": medicine_in_rag,
                "api_key_used": api_key_used,
                "user_context_applied": bool(user_context)
            }
            return CameraScanRequest(
                detected_text=extracted_text if extracted_text else "N/A",
                medicine_name=medicine_name,
                brand_name=brand_name if brand_name and brand_name.upper() not in ["UNKNOWN", "N/A", ""] else None,
                generic_name=generic_name if generic_name and generic_name.upper() not in ["UNKNOWN", "N/A", ""] else None,
                dosage=dosage if dosage and dosage.upper() not in ["UNKNOWN", "N/A", ""] else None,
                manufacturer=manufacturer if manufacturer and manufacturer.upper() not in ["UNKNOWN", "N/A", ""] else None,
                confidence=confidence,
                source=source,
                sources=sources_list,
                metadata=response_metadata,
                medicine_info=medicine_info
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error generating medicine information: {str(e)}"
            )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Error parsing image data: {str(e)}")
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Error scanning medicine image: {str(e)}")
@router.get("/{medicine_name}", response_model=MedicineInfo)
async def get_medicine_info(
    medicine_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific medicine.
    Args:
        medicine_name: Name of the medicine to look up
        current_user: Authenticated user (required)
        db: Database session
    Returns:
        Detailed medicine information including usage, side effects, alternatives
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available. Install required packages: langchain, chromadb, google-generativeai"
        )
    try:
        vectordb = get_retriever()
        query = f"medicine drug {medicine_name} usage side effects alternatives"
        docs = vectordb.similarity_search(query, k=5)
        medicine_docs = []
        for doc in docs:
            metadata = doc.metadata
            content_lower = doc.page_content.lower()
            medicine_lower = medicine_name.lower()
            if medicine_lower in content_lower or metadata.get("source") == "DrugBank":
                medicine_docs.append(doc)
        context = "\n\n".join([d.page_content for d in medicine_docs[:3]])
        has_meaningful_context = (
            len(medicine_docs) > 0 and 
            len(context.strip()) > 100 and
            medicine_name.lower() in context.lower()
        )
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        user_context = ""
        if current_user.age:
            user_context += f"\nUser age: {current_user.age} years old"
        if current_user.gender:
            user_context += f"\nUser gender: {current_user.gender}"
        if has_meaningful_context:
            prompt = f"""You are a medical information expert. Provide detailed information about the medicine: {medicine_name}
Context from medical databases:
{context}
{user_context}
Please provide the following information in a structured format, personalized for the user when relevant:
1. DESCRIPTION: Brief overview of what this medicine is
2. USAGE: What conditions it treats and how it's used
3. SIDE EFFECTS: List common side effects (as bullet points)
4. ALTERNATIVES: List alternative medicines or treatments
5. WARNINGS: Important warnings or precautions{' (consider age and gender if relevant)' if user_context else ''}
Format your response as JSON with these exact keys:
- description
- usage
- side_effects (array of strings)
- alternatives (array of strings)
- warnings
Be factual, clear, and concise. If information is not available in the context, state that clearly."""
        else:
            prompt = f"""You are a medical information expert. Provide comprehensive and accurate information about the medicine: {medicine_name}
{user_context}
Please provide the following information in a structured format{', personalized for the user age and gender when relevant' if user_context else ''}:
1. DESCRIPTION: Brief overview of what this medicine is, its chemical composition, and drug class
2. USAGE: What conditions it treats, how it's administered, typical dosages, and duration
3. SIDE EFFECTS: List all common and serious side effects (as detailed bullet points)
4. ALTERNATIVES: List alternative medicines with similar effects or from the same drug class
5. WARNINGS: Important warnings, precautions, contraindications, and drug interactions
Format your response as JSON with these exact keys:
- description (string)
- usage (string)
- side_effects (array of strings)
- alternatives (array of strings)
- warnings (string)
Provide accurate medical information based on your knowledge. Be comprehensive and detailed."""
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        import json
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text
            parsed_data = json.loads(json_text)
            def to_list_of_str(x):
                if x is None:
                    return ["Information not available"]
                if isinstance(x, str):
                    return [x]
                if isinstance(x, (list, tuple)):
                    return [str(i) for i in x]
                return [str(x)]
            def to_str(x):
                if x is None:
                    return "Consult a healthcare professional"
                if isinstance(x, str):
                    return x
                if isinstance(x, (list, tuple)):
                    return "; ".join([str(i) for i in x])
                return str(x)
            description = parsed_data.get("description", "Information not available")
            usage = parsed_data.get("usage", "Usage information not available")
            side_effects_list = to_list_of_str(parsed_data.get("side_effects"))
            side_effects = "\n".join([f"• {item}" for item in side_effects_list])
            alternatives_list = to_list_of_str(parsed_data.get("alternatives"))
            alternatives = "\n".join([f"• {item}" for item in alternatives_list])
            warnings = to_str(parsed_data.get("warnings"))
            try:
                import json as json_lib
                response_summary = json_lib.dumps({
                    "description": description[:200],
                    "usage": usage[:200],
                    "side_effects": side_effects_list[:3] if len(side_effects_list) > 3 else side_effects_list,
                    "alternatives": alternatives_list[:3] if len(alternatives_list) > 3 else alternatives_list
                })
                search_entry = SearchHistory(
                    user_id=current_user.id,
                    search_query=medicine_name,
                    search_response=response_summary,
                    search_type="medicine",
                    results_count=1
                )
                db.add(search_entry)
                db.commit()
            except Exception as e:
                pass

            return MedicineInfo(
                medicine_name=medicine_name,
                description=description,
                usage=usage,
                side_effects=side_effects,
                alternatives=alternatives,
                warnings=warnings,
                source="MedChat RAG Database"
            )
        except json.JSONDecodeError:
            return MedicineInfo(
                medicine_name=medicine_name,
                description=response_text[:200],
                usage="Please consult the full response for usage information",
                side_effects="• Refer to full response for side effects",
                alternatives="• Consult a healthcare professional for alternatives",
                warnings="Always consult a healthcare professional before taking any medication",
                source="MedChat RAG Database"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving medicine information: {str(e)}"
        )
@router.get("/search/", response_model=MedicineSearchResult)
async def search_medicines(
    query: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for medicines by name or condition.
    Args:
        query: Search query (medicine name or condition)
        limit: Maximum number of results to return
        current_user: Authenticated user (required)
        db: Database session
    Returns:
        List of matching medicines with brief information
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available. Install required packages."
        )
    try:
        vectordb = get_retriever()
        
        # Try multiple search variations to handle typos and misspellings
        search_variations = [
            query,  # Original query
            f"medicine drug treatment {query}",  # With medical context
        ]
        
        # Add common medicine name variations
        query_lower = query.lower().strip()
        
        # Common typo corrections for popular medicines
        typo_corrections = {
            'asprin': 'aspirin',
            'panadol': 'paracetamol acetaminophen',
            'brufen': 'ibuprofen',
            'paracetomol': 'paracetamol',
            'ibuprofin': 'ibuprofen',
            'amoxicilin': 'amoxicillin',
            'penicilin': 'penicillin',
            'omeprazol': 'omeprazole',
        }
        
        # Add corrected spelling if found
        if query_lower in typo_corrections:
            search_variations.insert(0, typo_corrections[query_lower])
        
        # Search with all variations
        all_docs = []
        seen_content = set()
        
        for search_query in search_variations:
            try:
                docs = vectordb.similarity_search(search_query, k=limit)
                for doc in docs:
                    # Avoid duplicates
                    content_hash = hash(doc.page_content[:100])
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        all_docs.append(doc)
                        if len(all_docs) >= limit:
                            break
                if len(all_docs) >= limit:
                    break
            except:
                continue
        
        # If still no results, try very broad search
        if len(all_docs) == 0:
            try:
                broad_query = f"{query} medication pharmaceutical drug"
                all_docs = vectordb.similarity_search(broad_query, k=limit)
            except:
                pass
        
        results = []
        for doc in all_docs[:limit]:
            results.append({
                "content": doc.page_content[:200] + "...",
                "metadata": doc.metadata,
                "relevance_score": doc.metadata.get("score", 0)
            })
        
        # Save search history
        try:
            search_history = SearchHistory(
                user_id=current_user.id,
                search_query=query,
                search_type="medicine",
                results_count=len(results)
            )
            db.add(search_history)
            db.commit()
        except:
            pass  # Don't fail if history save fails
        
        return MedicineSearchResult(
            query=query,
            results=results,
            total_found=len(results)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching medicines: {str(e)}"
        )
@router.get("/compare/")
async def compare_medicines(
    medicine1: str,
    medicine2: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare two medicines side by side.
    Args:
        medicine1: First medicine name
        medicine2: Second medicine name
        current_user: Authenticated user (required)
        db: Database session
    Returns:
        Comparison of both medicines
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available."
        )
    try:
        info1 = await get_medicine_info(medicine1)
        info2 = await get_medicine_info(medicine2)
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""Compare these two medicines:
Medicine 1: {medicine1}
- Usage: {info1.usage}
- Side Effects: {', '.join(info1.side_effects)}
Medicine 2: {medicine2}
- Usage: {info2.usage}
- Side Effects: {', '.join(info2.side_effects)}
Provide a brief comparison highlighting:
1. Key differences
2. Which might be better for what conditions
3. Safety considerations
Keep it factual and concise."""
        response = model.generate_content(prompt)
        return {
            "medicine1": info1,
            "medicine2": info2,
            "comparison": response.text
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error comparing medicines: {str(e)}"
        )
