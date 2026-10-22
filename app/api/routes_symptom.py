"""
Symptom Checker - Match symptoms to possible conditions
Route: POST /symptom-checker
Purpose: User enters symptoms → returns possible related conditions (information only)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session

# Core imports (required)
from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.chat import SearchHistory

try:
    from app.rag.retriever import get_retriever
    from app.core.config import settings
    import google.generativeai as genai
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

router = APIRouter(prefix="/api/v1/symptom", tags=["Symptom Checker"])


class SymptomCheckRequest(BaseModel):
    """Request model for symptom checking"""
    symptoms: List[str] = Field(..., description="List of symptoms", min_items=1)
    age: Optional[int] = Field(None, description="Patient age (optional)", ge=0, le=120)
    gender: Optional[str] = Field(None, description="Patient gender (optional)")
    duration: Optional[str] = Field(None, description="How long symptoms have been present")


class PossibleCondition(BaseModel):
    """A possible condition based on symptoms"""
    condition_name: str
    likelihood: str  # "High", "Medium", "Low"
    matching_symptoms: List[str]
    additional_symptoms: List[str]
    when_to_see_doctor: str
    brief_description: str


class SymptomCheckResponse(BaseModel):
    """Response model for symptom checking"""
    submitted_symptoms: List[str]
    possible_conditions: List[PossibleCondition]
    general_advice: str
    disclaimer: str = "This is for informational purposes only and not a medical diagnosis. Please consult a healthcare professional for proper evaluation."


@router.post("/check", response_model=SymptomCheckResponse)
async def check_symptoms(
    request: SymptomCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check symptoms and return possible conditions.
    
    **IMPORTANT DISCLAIMER**: This is for informational purposes only. 
    It does NOT provide medical diagnosis. Always consult a healthcare professional.
    
    Args:
        request: Symptom check request with list of symptoms
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        Possible conditions with likelihood and recommendations
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available. Install required packages."
        )
    
    try:
        # Get retriever instance
        # Get retriever instance (returns vectordb directly)
        vectordb = get_retriever()
        
        # Create search query from symptoms
        symptoms_text = ", ".join(request.symptoms)
        query = f"symptoms {symptoms_text} conditions diseases causes"
        
        # Search for relevant medical information
        docs = vectordb.similarity_search(query, k=5)
        
        # Combine context from retrieved documents
        context = "\n\n".join([d.page_content for d in docs[:5]])
        
        # Check if we have meaningful context
        has_context = len(docs) > 0 and len(context.strip()) > 100
        
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Build detailed prompt
        demographic_info = ""
        if request.age:
            demographic_info += f"\nPatient age: {request.age} years"
        if request.gender:
            demographic_info += f"\nPatient gender: {request.gender}"
        if request.duration:
            demographic_info += f"\nSymptom duration: {request.duration}"
        
        if has_context:
            # Use local RAG data
            prompt = f"""You are a medical information assistant. Based on the following symptoms, provide possible conditions for INFORMATIONAL PURPOSES ONLY (not a diagnosis).

Symptoms reported:
{symptoms_text}
{demographic_info}

Medical context from databases:
{context}

Please provide:
1. Top 3-5 possible conditions that could cause these symptoms
2. For each condition, indicate:
   - Likelihood (High/Medium/Low) based on symptom match
   - Which symptoms match
   - Additional symptoms to watch for
   - When to see a doctor (urgency level)
   - Brief description

Format as JSON with this structure:
{{
  "conditions": [
    {{
      "condition_name": "...",
      "likelihood": "High/Medium/Low",
      "matching_symptoms": [...],
      "additional_symptoms": [...],
      "when_to_see_doctor": "...",
      "brief_description": "..."
    }}
  ],
  "general_advice": "..."
}}

IMPORTANT: 
- Emphasize this is NOT a diagnosis
- Recommend seeing a healthcare professional
- If symptoms suggest emergency, clearly state to seek immediate medical attention
- Be factual and evidence-based"""
        else:
            # Fallback to Gemini AI when no local RAG data available
            prompt = f"""You are a medical information assistant. Based on the following symptoms, provide comprehensive possible conditions for INFORMATIONAL PURPOSES ONLY (not a diagnosis).

Symptoms reported:
{symptoms_text}
{demographic_info}

Provide:
1. Top 3-5 possible conditions that could cause these symptoms
2. For each condition, indicate:
   - Likelihood (High/Medium/Low) based on symptom match and medical knowledge
   - Which symptoms match
   - Additional symptoms to watch for
   - When to see a doctor (urgency level with specific red flags)
   - Brief description with causes and risk factors

Format as JSON with this structure:
{{
  "conditions": [
    {{
      "condition_name": "...",
      "likelihood": "High/Medium/Low",
      "matching_symptoms": [...],
      "additional_symptoms": [...],
      "when_to_see_doctor": "...",
      "brief_description": "..."
    }}
  ],
  "general_advice": "..."
}}

CRITICAL: 
- Emphasize this is NOT a diagnosis
- Recommend seeing a healthcare professional
- If symptoms suggest emergency (e.g., chest pain, difficulty breathing, severe bleeding), clearly state to seek IMMEDIATE medical attention
- Be comprehensive, accurate, and evidence-based
- Include both common and serious potential causes"""

        # Generate response using Gemini (no Google Search grounding)
        response = model.generate_content(prompt)
        
        response_text = response.text.strip()
        
        # Parse JSON response
        import json
        try:
            # Extract JSON from response
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
            
            # Convert to response model
            conditions = []
            for cond in parsed_data.get("conditions", [])[:5]:  # Limit to 5 conditions
                conditions.append(PossibleCondition(
                    condition_name=cond.get("condition_name", "Unknown"),
                    likelihood=cond.get("likelihood", "Unknown"),
                    matching_symptoms=cond.get("matching_symptoms", []),
                    additional_symptoms=cond.get("additional_symptoms", []),
                    when_to_see_doctor=cond.get("when_to_see_doctor", "Consult a healthcare professional"),
                    brief_description=cond.get("brief_description", "")
                ))
            
            # Save search history for personalization
            try:
                search_entry = SearchHistory(
                    user_id=current_user.id,
                    query=", ".join(request.symptoms),
                    search_type="symptom",
                    results_count=len(conditions)
                )
                db.add(search_entry)
                db.commit()
            except Exception as e:
                print(f"Warning: Could not save search history: {e}")
            
            return SymptomCheckResponse(
                submitted_symptoms=request.symptoms,
                possible_conditions=conditions,
                general_advice=parsed_data.get("general_advice", "Please consult a healthcare professional for proper evaluation and diagnosis.")
            )
            
        except json.JSONDecodeError:
            # Fallback response if JSON parsing fails
            return SymptomCheckResponse(
                submitted_symptoms=request.symptoms,
                possible_conditions=[
                    PossibleCondition(
                        condition_name="Multiple Possibilities",
                        likelihood="Unknown",
                        matching_symptoms=request.symptoms,
                        additional_symptoms=[],
                        when_to_see_doctor="Consult a healthcare professional for proper evaluation",
                        brief_description=response_text[:300]
                    )
                ],
                general_advice="Please consult a healthcare professional for a proper diagnosis. The symptoms you described could have multiple causes."
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking symptoms: {str(e)}"
        )


@router.post("/emergency-check")
async def check_emergency_symptoms(
    symptoms: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Quick check for emergency symptoms that require immediate medical attention.
    
    Args:
        symptoms: List of symptoms
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        Whether symptoms suggest emergency and recommendations
    """
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available."
        )
    
    # Emergency symptom keywords
    emergency_keywords = [
        "chest pain", "difficulty breathing", "severe bleeding", "unconscious",
        "stroke", "heart attack", "severe headache", "high fever", "seizure",
        "severe abdominal pain", "sudden vision loss", "severe allergic reaction",
        "suicide", "overdose", "poisoning", "severe burn", "severe injury"
    ]
    
    # Check for emergency keywords
    is_potential_emergency = False
    matched_emergency = []
    
    symptoms_lower = [s.lower() for s in symptoms]
    for symptom in symptoms_lower:
        for emergency in emergency_keywords:
            if emergency in symptom:
                is_potential_emergency = True
                matched_emergency.append(emergency)
    
    try:
        # Get AI assessment
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        symptoms_text = ", ".join(symptoms)
        prompt = f"""Assess if these symptoms suggest a medical emergency requiring immediate attention:

Symptoms: {symptoms_text}

Respond with JSON:
{{
  "is_emergency": true/false,
  "urgency_level": "Immediate/Urgent/Non-urgent",
  "reason": "...",
  "action": "..."
}}"""

        response = model.generate_content(prompt)
        
        # Parse response
        import json
        response_text = response.text.strip()
        
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text
            
        assessment = json.loads(json_text)
        
        return {
            "symptoms": symptoms,
            "is_potential_emergency": is_potential_emergency or assessment.get("is_emergency", False),
            "matched_emergency_keywords": matched_emergency,
            "urgency_level": assessment.get("urgency_level", "Unknown"),
            "reason": assessment.get("reason", ""),
            "recommended_action": assessment.get("action", "Consult a healthcare professional"),
            "emergency_services": {
                "us": "911",
                "uk": "999",
                "eu": "112",
                "message": "If this is a life-threatening emergency, call emergency services immediately."
            }
        }
        
    except Exception as e:
        # Safety-first fallback
        return {
            "symptoms": symptoms,
            "is_potential_emergency": is_potential_emergency,
            "matched_emergency_keywords": matched_emergency,
            "urgency_level": "Seek medical evaluation",
            "reason": "Unable to assess automatically. Please consult a healthcare professional.",
            "recommended_action": "If you believe this is an emergency, call emergency services immediately. Otherwise, consult a healthcare professional as soon as possible.",
            "emergency_services": {
                "us": "911",
                "uk": "999",
                "eu": "112"
            },
            "error": str(e)
        }


@router.get("/common-conditions")
async def get_common_conditions():
    """
    Get a list of common medical conditions with their typical symptoms.
    
    Returns:
        List of common conditions and their symptoms
    """
    common_conditions = [
        {
            "name": "Common Cold",
            "typical_symptoms": ["runny nose", "sore throat", "cough", "sneezing", "mild fever"],
            "duration": "7-10 days",
            "severity": "Mild"
        },
        {
            "name": "Influenza (Flu)",
            "typical_symptoms": ["high fever", "body aches", "fatigue", "cough", "headache"],
            "duration": "1-2 weeks",
            "severity": "Moderate"
        },
        {
            "name": "Migraine",
            "typical_symptoms": ["severe headache", "nausea", "light sensitivity", "visual disturbances"],
            "duration": "4-72 hours",
            "severity": "Moderate to Severe"
        },
        {
            "name": "Gastroenteritis",
            "typical_symptoms": ["diarrhea", "nausea", "vomiting", "stomach cramps", "fever"],
            "duration": "1-3 days",
            "severity": "Mild to Moderate"
        },
        {
            "name": "Allergic Rhinitis",
            "typical_symptoms": ["sneezing", "itchy eyes", "runny nose", "congestion"],
            "duration": "Seasonal or chronic",
            "severity": "Mild"
        },
        {
            "name": "Urinary Tract Infection",
            "typical_symptoms": ["burning urination", "frequent urination", "lower abdominal pain", "cloudy urine"],
            "duration": "3-7 days with treatment",
            "severity": "Mild to Moderate"
        }
    ]
    
    return {
        "common_conditions": common_conditions,
        "disclaimer": "This list is for informational purposes only. Consult a healthcare professional for proper diagnosis."
    }
