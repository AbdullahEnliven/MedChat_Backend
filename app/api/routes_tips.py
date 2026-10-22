"""
Daily Health Tips - AI Wellness Feed
Route: GET /tips/{category}
Purpose: Generate personalized daily wellness tips
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

# Core imports (required)
from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.chat import SearchHistory, HealthProfile

try:
    from app.core.config import settings
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

router = APIRouter(prefix="/api/v1/tips", tags=["Health Tips"])


class HealthTip(BaseModel):
    """A single health tip"""
    title: str
    description: str
    category: str
    difficulty: str  # "Easy", "Medium", "Hard"
    estimated_time: Optional[str] = None


class HealthTipsResponse(BaseModel):
    """Response model for health tips"""
    category: str
    tips: List[HealthTip]
    generated_at: str
    tip_of_the_day: Optional[str] = None


AVAILABLE_CATEGORIES = [
    "diet", "nutrition", "fitness", "exercise", "sleep", "mental_health",
    "stress_management", "hydration", "meditation", "yoga", "cardio",
    "strength_training", "weight_loss", "heart_health", "immune_system",
    "skin_care", "dental_health", "eye_health", "bone_health", "digestive_health"
]


@router.get("/categories")
async def get_categories():
    """
    Get list of available tip categories.
    
    Returns:
        List of all available health tip categories
    """
    return {
        "categories": AVAILABLE_CATEGORIES,
        "total": len(AVAILABLE_CATEGORIES),
        "description": "Select a category to get personalized health tips"
    }


@router.get("/{category}", response_model=HealthTipsResponse)
async def get_health_tips(
    category: str,
    count: int = Query(5, ge=1, le=10, description="Number of tips to generate"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized health and wellness tips based on user's search history.
    
    Args:
        category: Health category (diet, fitness, sleep, mental_health, etc.)
        count: Number of tips to generate (1-10)
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        List of practical, evidence-based health tips personalized for the user
    """
    if not AI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI system not available. Install google-generativeai package."
        )
    
    # Normalize category
    category = category.lower().replace("-", "_").replace(" ", "_")
    
    if category not in AVAILABLE_CATEGORIES:
        # Try to find similar category
        similar = [c for c in AVAILABLE_CATEGORIES if category in c or c in category]
        if similar:
            category = similar[0]
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Available categories: {', '.join(AVAILABLE_CATEGORIES)}"
            )
    
    try:
        # Get user's recent search history for personalization
        recent_searches = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id
        ).order_by(SearchHistory.timestamp.desc()).limit(10).all()
        
        # Get user's health profile if it exists
        health_profile = db.query(HealthProfile).filter(
            HealthProfile.user_id == current_user.id
        ).first()
        
        # Build personalization context
        personalization = ""
        if recent_searches:
            search_topics = list(set([s.search_query for s in recent_searches]))[:5]
            personalization = f"\n\nPersonalization Context (user has been researching): {', '.join(search_topics)}"
            personalization += "\nTailor tips to be relevant to these health interests."
        
        if health_profile:
            profile_info = []
            if health_profile.allergies:
                profile_info.append(f"allergies: {health_profile.allergies}")
            if health_profile.medications:
                profile_info.append(f"medications: {health_profile.medications}")
            if health_profile.medical_conditions:
                profile_info.append(f"conditions: {health_profile.medical_conditions}")
            if profile_info:
                personalization += f"\nUser Health Profile: {', '.join(profile_info)}"
                personalization += "\nEnsure tips are safe and relevant considering this profile."
        
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Create personalized prompt for generating tips
        prompt = f"""Generate {count} practical, evidence-based health tips for the category: {category.replace('_', ' ').title()}{personalization}

Requirements:
- Each tip should be actionable and specific
- Include difficulty level (Easy/Medium/Hard)
- Estimate time needed to implement (if applicable)
- Base recommendations on scientific evidence
- Make tips suitable for this specific user
- Keep each tip concise but informative
- If user has health conditions/allergies, ensure tips are safe

Format as JSON:
{{
  "tips": [
    {{
      "title": "Short catchy title",
      "description": "Detailed explanation and how to implement",
      "difficulty": "Easy/Medium/Hard",
      "estimated_time": "5 minutes/30 minutes/daily/etc."
    }}
  ],
  "tip_of_the_day": "One standout tip as a quick summary"
}}

Categories context:
- diet/nutrition: healthy eating, meal planning, nutrients
- fitness/exercise: workouts, physical activity, training
- sleep: sleep hygiene, rest, recovery
- mental_health: stress, anxiety, emotional wellbeing
- hydration: water intake, fluid balance
- meditation/yoga: mindfulness, relaxation techniques"""

        # Generate tips
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON response
        import json
        try:
            # Extract JSON
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
            tips = []
            for tip_data in parsed_data.get("tips", [])[:count]:
                tips.append(HealthTip(
                    title=tip_data.get("title", "Health Tip"),
                    description=tip_data.get("description", ""),
                    category=category,
                    difficulty=tip_data.get("difficulty", "Easy"),
                    estimated_time=tip_data.get("estimated_time")
                ))
            
            return HealthTipsResponse(
                category=category.replace("_", " ").title(),
                tips=tips,
                generated_at=datetime.now().isoformat(),
                tip_of_the_day=parsed_data.get("tip_of_the_day")
            )
            
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            raise HTTPException(
                status_code=500,
                detail="Error parsing AI response. Please try again."
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating health tips: {str(e)}"
        )


@router.get("/daily/random")
async def get_daily_tip(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a random health tip for the day.
    
    Args:
        current_user: Authenticated user (required)
        db: Database session
    
    Returns:
        One random health tip from any category
    """
    if not AI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI system not available."
        )
    
    import random
    import json
    
    try:
        # Select random category
        category = random.choice(AVAILABLE_CATEGORIES)
        
        # Generate a single tip directly without ChromaDB dependency
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Generate one practical health tip for {category.replace('_', ' ').title()}.

Provide a quick, actionable tip that anyone can use today.

Format as JSON:
{{
  "title": "Short catchy title",
  "description": "Brief explanation (2-3 sentences)",
  "difficulty": "Easy",
  "category": "{category}"
}}"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON response
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
        
        tip_data = json.loads(json_text)
        
        return {
            "tip_of_the_day": tip_data,
            "category": category.replace("_", " ").title(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "message": "Here's your health tip for today!"
        }
        
    except Exception as e:
        # Fallback tip
        return {
            "tip_of_the_day": {
                "title": "Stay Hydrated",
                "description": "Drink at least 8 glasses of water throughout the day. Proper hydration supports your body's vital functions and helps maintain energy levels.",
                "difficulty": "Easy",
                "category": "Hydration"
            },
            "category": "General Health",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "message": "Here's your health tip for today!"
        }


@router.post("/personalized")
async def get_personalized_tips(
    goals: List[str],
    preferences: Optional[List[str]] = None,
    restrictions: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized health tips based on user goals and preferences.
    
    Args:
        goals: List of health goals (e.g., "lose weight", "build muscle", "reduce stress")
        preferences: Optional preferences (e.g., "vegetarian", "home workouts")
        restrictions: Optional restrictions (e.g., "no dairy", "limited time")
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        Personalized health tips tailored to user profile
    """
    if not AI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI system not available."
        )
    
    try:
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        goals_text = ", ".join(goals)
        preferences_text = ", ".join(preferences) if preferences else "None specified"
        restrictions_text = ", ".join(restrictions) if restrictions else "None specified"
        
        prompt = f"""Create personalized health and wellness recommendations based on:

Goals: {goals_text}
Preferences: {preferences_text}
Restrictions: {restrictions_text}

Generate 5-7 specific, actionable tips that:
1. Align with the stated goals
2. Respect preferences and restrictions
3. Are evidence-based and safe
4. Include practical implementation steps
5. Cover multiple aspects (diet, exercise, lifestyle)

Format as JSON with tips array, each containing:
- title
- description
- category
- difficulty
- why_it_helps (specific to their goals)"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse response
        import json
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text
            
        parsed_data = json.loads(json_text)
        
        return {
            "goals": goals,
            "preferences": preferences,
            "restrictions": restrictions,
            "personalized_tips": parsed_data.get("tips", []),
            "generated_at": datetime.now().isoformat(),
            "note": "These tips are personalized based on your input. Consult healthcare professionals before making significant lifestyle changes."
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating personalized tips: {str(e)}"
        )


@router.get("/challenge/{category}")
async def get_wellness_challenge(
    category: str,
    duration_days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a wellness challenge for a specific category.
    
    Args:
        category: Health category for the challenge
        duration_days: Challenge duration in days (1-30)
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        A structured wellness challenge with daily goals
    """
    if not AI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI system not available."
        )
    
    category = category.lower().replace("-", "_").replace(" ", "_")
    
    if category not in AVAILABLE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Available: {', '.join(AVAILABLE_CATEGORIES)}"
        )
    
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Create a {duration_days}-day wellness challenge for: {category.replace('_', ' ').title()}

Design a progressive challenge that:
1. Starts easy and gradually increases difficulty
2. Has clear daily goals
3. Is achievable for beginners
4. Builds healthy habits
5. Includes tracking methods

Format as JSON:
{{
  "challenge_name": "...",
  "description": "...",
  "duration_days": {duration_days},
  "daily_goals": [
    {{"day": 1, "goal": "...", "description": "...", "tips": ["..."]}},
    ...
  ],
  "success_metrics": ["..."],
  "rewards": "What benefits to expect"
}}"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        import json
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text
            
        challenge = json.loads(json_text)
        challenge["category"] = category.replace("_", " ").title()
        challenge["start_date"] = datetime.now().strftime("%Y-%m-%d")
        
        return challenge
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating wellness challenge: {str(e)}"
        )
