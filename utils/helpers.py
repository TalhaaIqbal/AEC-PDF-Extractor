"""
Utility Helper Functions
Common utility functions used across the application
"""
import json
import io
import base64
from typing import Optional, Any
from PIL import Image
from config.settings import MAX_CONTEXT_CHARS, LLM_MAX_IMAGE_DIMENSION


def compact_json(data: Any, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Compact JSON to fit within context limits
    Prioritizes text data over path data if truncation is needed
    
    Args:
        data: Data to be JSON serialized
        max_chars: Maximum characters for the output
    
    Returns:
        Compact JSON string
    """
    if not data:
        return ""

    try:
        # If data has both texts and paths, prioritize texts
        if isinstance(data, dict) and "texts" in data and "paths" in data:
            texts_json = json.dumps({"texts": data["texts"]}, ensure_ascii=False, separators=(",", ":"))
            
            # If texts alone fit, add paths summary
            if len(texts_json) < max_chars * 0.8:  # Reserve 20% for paths
                paths_json = json.dumps({"paths": data["paths"]}, ensure_ascii=False, separators=(",", ":"))
                combined = texts_json[:-1] + ", " + paths_json[1:]
                if len(combined) <= max_chars:
                    return combined
                else:
                    # Fit paths in remaining space
                    remaining = max_chars - len(texts_json) - 2  # 2 for ", "
                    if remaining > 50:  # Only add paths if meaningful space remains
                        paths_truncated = paths_json[:remaining] + "...}"
                        combined = texts_json[:-1] + ", " + paths_truncated[1:]
                        return combined
                    return texts_json
            else:
                # Texts alone exceed limit, truncate texts
                return texts_json[:max_chars] + "\n...[TRUNCATED FOR CONTEXT LIMIT]..."
        
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(data)[:max_chars]

    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[TRUNCATED FOR CONTEXT LIMIT]..."

    return text


def image_to_data_url(image_path: str, max_dimension: int = LLM_MAX_IMAGE_DIMENSION) -> str:
    """
    Convert image to base64 data URL
    
    Args:
        image_path: Path to the image file
        max_dimension: Maximum dimension for image resizing (kept for compatibility, 
                      but images should already be rendered at optimal size)
    
    Returns:
        Base64 data URL string
    """
    img = Image.open(image_path).convert("RGB")

    # Resize only if image exceeds max_dimension (safety check)
    original_width, original_height = img.size
    max_original = max(original_width, original_height)
    scale = min(1.0, max_dimension / max_original)

    if scale < 1.0:
        new_size = (int(original_width * scale), int(original_height * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded}"


def parse_llm_json(text: str, page_index: Optional[int] = None) -> Dict[str, Any]:
    """
    Parse JSON from LLM response with fallback handling
    
    Args:
        text: Text response from LLM
        page_index: Optional page index for error reporting
    
    Returns:
        Parsed JSON dictionary or error dictionary
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return {
        "page": (page_index + 1) if page_index is not None else None,
        "detection_status": "error",
        "error": "Invalid JSON returned",
        "raw_output": text
    }
