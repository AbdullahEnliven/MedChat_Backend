"""
OCR Utility for Medicine Name Extraction
Extracts text from medicine images using Tesseract OCR
"""

import io
import re
from typing import List, Optional
from PIL import Image
import pytesseract

# Configure Tesseract path (adjust for Windows)
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR accuracy.
    
    Args:
        image: PIL Image object
        
    Returns:
        Preprocessed PIL Image
    """
    # Convert to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize if too large (max 2000px)
    max_size = 2000
    if image.width > max_size or image.height > max_size:
        ratio = min(max_size / image.width, max_size / image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to grayscale for better OCR
    image = image.convert('L')
    
    # Increase contrast
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    return image


def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from image using OCR.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        Extracted text string
    """
    try:
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Preprocess
        processed_image = preprocess_image(image)
        
        # Extract text using Tesseract
        text = pytesseract.image_to_string(processed_image)
        
        return text.strip()
        
    except Exception as e:
        raise ValueError(f"Error extracting text from image: {str(e)}")


def extract_medicine_name(text: str) -> Optional[str]:
    """
    Extract likely medicine name from OCR text.
    Uses heuristics to identify the most likely medicine name.
    
    Args:
        text: Raw OCR text
        
    Returns:
        Extracted medicine name or None
    """
    if not text:
        return None
    
    # Clean text
    lines = text.strip().split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        return None
    
    # Heuristics for medicine name detection:
    # 1. Usually in uppercase or title case
    # 2. Often appears at the top of the label
    # 3. Typically 2-15 characters for generic names
    # 4. May contain alphanumeric characters
    
    candidates = []
    
    for line in lines[:5]:  # Check first 5 lines
        # Remove special characters but keep spaces and hyphens
        cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', '', line)
        cleaned = cleaned.strip()
        
        # Skip if too short or too long
        if len(cleaned) < 3 or len(cleaned) > 50:
            continue
        
        # Skip common non-medicine words
        skip_words = ['tablet', 'capsule', 'mg', 'ml', 'dose', 'take', 'use', 
                     'warning', 'caution', 'prescription', 'pharmacy', 'medicine',
                     'drug', 'manufactured', 'expiry', 'batch']
        
        if any(word in cleaned.lower() for word in skip_words):
            continue
        
        # Prefer uppercase or title case words
        if cleaned.isupper() or cleaned.istitle():
            candidates.insert(0, cleaned)
        else:
            candidates.append(cleaned)
    
    # Return the first (most likely) candidate
    return candidates[0] if candidates else (lines[0] if lines else None)


def extract_medicine_names_from_image(image_bytes: bytes) -> List[str]:
    """
    Complete pipeline: Extract text from image and identify medicine name(s).
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        List of possible medicine names (ordered by confidence)
    """
    # Extract all text
    text = extract_text_from_image(image_bytes)
    
    if not text:
        return []
    
    # Get primary medicine name
    medicine_name = extract_medicine_name(text)
    
    if not medicine_name:
        # Fallback: return cleaned first line
        lines = text.strip().split('\n')
        if lines:
            first_line = re.sub(r'[^a-zA-Z0-9\s\-]', '', lines[0]).strip()
            return [first_line] if first_line else []
        return []
    
    return [medicine_name]


def validate_tesseract_installation() -> bool:
    """
    Check if Tesseract is properly installed.
    
    Returns:
        True if Tesseract is available, False otherwise
    """
    try:
        version = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
