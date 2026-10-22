"""
Voice Input - Speech-to-Text API Integration
Route: POST /voice
Purpose: User speaks their question → converted to text → processed by RAG pipeline
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import io

try:
    from app.core.config import settings
    from app.core.database import get_db
    from app.utils.auth import get_current_user
    from app.models.user import User
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Check for speech recognition libraries
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    from app.rag.generator import get_medchat_answer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

router = APIRouter(prefix="/api/v1/voice", tags=["Voice Input"])


class VoiceQueryResponse(BaseModel):
    """Response model for voice queries"""
    transcribed_text: str
    answer: str
    sources: Optional[list] = None
    processing_time_ms: int


class VoiceTranscriptionResponse(BaseModel):
    """Response model for voice transcription only"""
    transcribed_text: str
    confidence: Optional[float] = None
    language: Optional[str] = None


@router.post("/query", response_model=VoiceQueryResponse)
async def voice_query(
    audio: UploadFile = File(..., description="Audio file (WAV, MP3, FLAC, etc.)"),
    language: str = Form("en-US", description="Language code (e.g., en-US, es-ES)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process voice query: convert speech to text and get medical answer.
    
    Args:
        audio: Audio file containing the voice query
        language: Language code for speech recognition
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        Transcribed text and AI answer
    """
    if not SPEECH_RECOGNITION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Speech recognition not available. Install: pip install SpeechRecognition pydub"
        )
    
    if not RAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="RAG system not available. Install required packages."
        )
    
    import time
    start_time = time.time()
    
    try:
        # Read audio file
        audio_data = await audio.read()
        
        # Convert to speech recognition format
        recognizer = sr.Recognizer()
        
        # Try to recognize the audio file format
        try:
            # Try as WAV first
            audio_file = sr.AudioFile(io.BytesIO(audio_data))
            with audio_file as source:
                audio_content = recognizer.record(source)
            
            # Recognize speech using Google Speech Recognition
            try:
                text = recognizer.recognize_google(audio_content, language=language)
            except sr.UnknownValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Could not understand audio. Please speak clearly and try again."
                )
            except sr.RequestError as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Speech recognition service error: {str(e)}"
                )
                
        except Exception as audio_error:
            # If WAV fails, try converting with pydub (if available)
            try:
                from pydub import AudioSegment
                import tempfile
                import os
                
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
                    temp_file.write(audio_data)
                    temp_path = temp_file.name
                
                # Convert to WAV
                audio_segment = AudioSegment.from_file(temp_path)
                wav_path = temp_path + ".wav"
                audio_segment.export(wav_path, format="wav")
                
                # Recognize from converted WAV
                with sr.AudioFile(wav_path) as source:
                    audio_content = recognizer.record(source)
                
                text = recognizer.recognize_google(audio_content, language=language)
                
                # Cleanup
                os.unlink(temp_path)
                os.unlink(wav_path)
                
            except ImportError:
                raise HTTPException(
                    status_code=400,
                    detail="Audio format not supported. Please upload WAV file or install pydub: pip install pydub"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing audio: {str(e)}"
                )
        
        # Get answer from RAG pipeline
        answer_data = get_medchat_answer(text)
        
        # Extract answer and sources
        if isinstance(answer_data, dict):
            answer = answer_data.get("answer", str(answer_data))
            sources = answer_data.get("sources", [])
        else:
            answer = str(answer_data)
            sources = []
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return VoiceQueryResponse(
            transcribed_text=text,
            answer=answer,
            sources=sources,
            processing_time_ms=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing voice query: {str(e)}"
        )


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("en-US"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transcribe audio to text without answering.
    
    Args:
        audio: Audio file to transcribe
        language: Language code
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        Transcribed text only
    """
    if not SPEECH_RECOGNITION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Speech recognition not available. Install SpeechRecognition."
        )
    
    try:
        audio_data = await audio.read()
        recognizer = sr.Recognizer()
        
        # Process audio
        try:
            audio_file = sr.AudioFile(io.BytesIO(audio_data))
            with audio_file as source:
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_content = recognizer.record(source)
            
            # Recognize with confidence
            alternatives = recognizer.recognize_google(
                audio_content,
                language=language,
                show_all=True
            )
            
            if alternatives and "alternative" in alternatives:
                best_result = alternatives["alternative"][0]
                text = best_result["transcript"]
                confidence = best_result.get("confidence", None)
            else:
                text = recognizer.recognize_google(audio_content, language=language)
                confidence = None
            
            return VoiceTranscriptionResponse(
                transcribed_text=text,
                confidence=confidence,
                language=language
            )
            
        except sr.UnknownValueError:
            raise HTTPException(
                status_code=400,
                detail="Could not understand audio"
            )
        except sr.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Speech recognition service error: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error transcribing audio: {str(e)}"
        )


@router.post("/text-to-speech")
async def text_to_speech(
    text: str,
    language: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Convert text to speech (if TTS is available).
    
    Args:
        text: Text to convert to speech
        language: Language code
        current_user: Authenticated user (required)
        db: Database session
        
    Returns:
        Audio file or URL to audio
    """
    try:
        from gtts import gTTS
        import tempfile
        from fastapi.responses import FileResponse
        
        # Generate speech
        tts = gTTS(text=text, lang=language, slow=False)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            tts.save(temp_file.name)
            temp_path = temp_file.name
        
        # Return audio file
        return FileResponse(
            temp_path,
            media_type="audio/mpeg",
            filename="response.mp3",
            headers={"Content-Disposition": "attachment; filename=response.mp3"}
        )
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Text-to-speech not available. Install: pip install gTTS"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating speech: {str(e)}"
        )


@router.get("/supported-languages")
async def get_supported_languages():
    """
    Get list of supported languages for speech recognition.
    
    Returns:
        List of supported language codes
    """
    languages = {
        "en-US": "English (United States)",
        "en-GB": "English (United Kingdom)",
        "en-AU": "English (Australia)",
        "en-IN": "English (India)",
        "es-ES": "Spanish (Spain)",
        "es-MX": "Spanish (Mexico)",
        "fr-FR": "French (France)",
        "de-DE": "German (Germany)",
        "it-IT": "Italian (Italy)",
        "pt-BR": "Portuguese (Brazil)",
        "pt-PT": "Portuguese (Portugal)",
        "ru-RU": "Russian (Russia)",
        "zh-CN": "Chinese (Mandarin, Simplified)",
        "ja-JP": "Japanese (Japan)",
        "ko-KR": "Korean (South Korea)",
        "ar-SA": "Arabic (Saudi Arabia)",
        "hi-IN": "Hindi (India)",
        "tr-TR": "Turkish (Turkey)",
        "pl-PL": "Polish (Poland)",
        "nl-NL": "Dutch (Netherlands)"
    }
    
    return {
        "supported_languages": languages,
        "total": len(languages),
        "note": "More languages may be supported by the underlying Google Speech Recognition service"
    }


@router.get("/audio-formats")
async def get_audio_formats():
    """
    Get list of supported audio formats.
    
    Returns:
        List of supported audio file formats
    """
    formats = {
        "native_support": [
            {"format": "WAV", "extension": ".wav", "description": "Waveform Audio File Format (recommended)"},
            {"format": "AIFF", "extension": ".aiff", "description": "Audio Interchange File Format"}
        ],
        "with_pydub": [
            {"format": "MP3", "extension": ".mp3", "description": "MPEG Audio Layer 3"},
            {"format": "FLAC", "extension": ".flac", "description": "Free Lossless Audio Codec"},
            {"format": "OGG", "extension": ".ogg", "description": "Ogg Vorbis"},
            {"format": "M4A", "extension": ".m4a", "description": "MPEG-4 Audio"},
            {"format": "WMA", "extension": ".wma", "description": "Windows Media Audio"}
        ]
    }
    
    return {
        "audio_formats": formats,
        "note": "WAV and AIFF are supported natively. Other formats require pydub: pip install pydub"
    }
