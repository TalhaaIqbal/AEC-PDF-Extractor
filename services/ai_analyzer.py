"""
AI Analyzer Service
Handles AI-powered analysis using OpenAI API
"""
import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from config.settings import MODEL, OPENAI_API_KEY
from utils.helpers import compact_json, image_to_data_url, parse_llm_json
from prompts import (
    load_system_prompt,
    format_page_analysis_prompt,
    format_consolidation_prompt,
    load_page_json_schema,
    load_final_schema,
    load_civil_schema,
    load_civil_system_prompt,
    load_civil_final_schema,
    load_civil_consolidation_prompt,
    format_civil_page_analysis_prompt,
    format_civil_consolidation_prompt
)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Load prompts and schemas at module level
SYSTEM_PROMPT = load_system_prompt()
PAGE_JSON_SCHEMA = load_page_json_schema()
FINAL_SCHEMA = load_final_schema()
CIVIL_SYSTEM_PROMPT = load_civil_system_prompt()
CIVIL_PAGE_JSON_SCHEMA = load_civil_schema()
CIVIL_FINAL_SCHEMA = load_civil_final_schema()


def detect_sheet_type(sheet_info: dict) -> str:
    """
    Detect if sheet is architectural, civil, structural, etc.
    
    Args:
        sheet_info: Dictionary containing sheet metadata
    
    Returns:
        Sheet type: "civil", "architectural", or "structural"
    """
    drawing_type = sheet_info.get("drawing_type", "").lower() if sheet_info else ""
    discipline = sheet_info.get("discipline", "").lower() if sheet_info else ""
    sheet_title = sheet_info.get("sheet_title", "").lower() if sheet_info else ""
    
    # Civil/roadway indicators
    civil_keywords = ["roadway", "civil", "site", "grading", "drainage", "utility", "landscape"]
    if any(keyword in drawing_type or keyword in discipline or keyword in sheet_title 
           for keyword in civil_keywords):
        return "civil"
    
    # Structural indicators
    structural_keywords = ["structural", "framing", "steel", "concrete"]
    if any(keyword in discipline for keyword in structural_keywords):
        return "structural"
    
    # Default to architectural
    return "architectural"


def extract_sheet_info_from_vector(texts: list) -> dict:
    """
    Extract sheet information from native PDF text spans
    
    Args:
        texts: List of text spans from vector data extraction
    
    Returns:
        Dictionary with sheet metadata (sheet_title, discipline, drawing_type)
    """
    sheet_info = {
        "sheet_title": "",
        "discipline": "",
        "drawing_type": ""
    }
    
    if not texts:
        return sheet_info
    
    # Combine all text for analysis
    all_text = " ".join([text_obj.get("text", "") for text_obj in texts])
    all_text_lower = all_text.lower()
    
    # Look for discipline indicators
    civil_keywords = ["roadway", "civil", "site", "grading", "drainage", "utility", "landscape"]
    structural_keywords = ["structural", "framing", "steel", "concrete"]
    
    for keyword in civil_keywords:
        if keyword in all_text_lower:
            sheet_info["discipline"] = keyword
            break
    
    for keyword in structural_keywords:
        if keyword in all_text_lower:
            sheet_info["discipline"] = keyword
            break
    
    # Look for drawing type indicators
    if "plan" in all_text_lower:
        sheet_info["drawing_type"] = "Plan"
    elif "section" in all_text_lower:
        sheet_info["drawing_type"] = "Section"
    elif "elevation" in all_text_lower:
        sheet_info["drawing_type"] = "Elevation"
    
    # Look for sheet title (usually the largest text or first significant text)
    for text_obj in texts:
        text = text_obj.get("text", "").strip()
        font_size = text_obj.get("font_size", 0)
        
        # Assume larger text is more likely to be title
        if font_size > 12 and len(text) > 5 and len(text) < 50:
            sheet_info["sheet_title"] = text
            break
    
    return sheet_info


def build_page_prompt(page_index: int, vector_data: Optional[Dict[str, Any]], sheet_type: str = "architectural") -> str:
    """
    Build prompt for page analysis based on sheet type
    
    Args:
        page_index: Index of the page being analyzed
        vector_data: Optional vector data for the page
        sheet_type: Type of drawing ("architectural", "civil", "structural")
    
    Returns:
        Formatted prompt string
    """
    # Increase character limit for text data since we removed detailed path data
    vector_text = compact_json(vector_data, max_chars=50000)
    
    if not vector_text:
        vector_text = "Not available - this page has no native vector data (likely a scanned/raster page)."

    if sheet_type == "civil":
        return format_civil_page_analysis_prompt(
            page_index=page_index + 1,
            vector_data=vector_text,
            page_json_schema=CIVIL_PAGE_JSON_SCHEMA
        )
    else:
        return format_page_analysis_prompt(
            page_index=page_index + 1,
            vector_data=vector_text,
            page_json_schema=PAGE_JSON_SCHEMA
        )


async def analyze_page(page_index: int, page_image_path: str, vector_data: Optional[Dict[str, Any]], sheet_type: str = "architectural") -> Dict[str, Any]:
    """
    Analyze a single page using LLM with single retry for truncated responses
    
    Args:
        page_index: Index of the page to analyze
        page_image_path: Path to the page image
        vector_data: Optional vector data for the page
        sheet_type: Type of drawing ("architectural", "civil", "structural")
    
    Returns:
        Analysis result dictionary
    """
    image_url = image_to_data_url(page_image_path)
    prompt = build_page_prompt(page_index, vector_data, sheet_type)
    
    # Select appropriate system prompt based on sheet type
    system_prompt = CIVIL_SYSTEM_PROMPT if sheet_type == "civil" else SYSTEM_PROMPT

    # Higher base limit with single retry
    base_tokens = 16384
    retry_tokens = 32768
    
    for attempt, max_tokens in enumerate([base_tokens, retry_tokens]):
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_completion_tokens=max_tokens
        )

        finish_reason = response.choices[0].finish_reason
        text = response.choices[0].message.content.strip()
        
        # If response was truncated and this is first attempt, retry once
        if finish_reason == "length" and attempt == 0:
            print(f"Page {page_index + 1}: Response truncated at {max_tokens} tokens, retrying once...")
            continue
        
        result = parse_llm_json(text, page_index)
        
        # Check if result has error from incomplete JSON and retry once
        if "error" in result and result.get("error") == "Invalid JSON returned" and attempt == 0:
            print(f"Page {page_index + 1}: Invalid JSON (possibly truncated), retrying once...")
            continue
        
        return result
    
    # If retry failed, return with warning
    result = parse_llm_json(text, page_index)
    if "error" not in result:
        result["warning"] = "Response may be truncated due to content length limits"
    return result


async def consolidate_results(page_results: list, sheet_type: str = "architectural") -> Dict[str, Any]:
    """
    Consolidate results from multiple pages using AI with single retry and work splitting
    
    Args:
        page_results: List of page analysis results
        sheet_type: Type of drawing ("architectural", "civil", "structural")
    
    Returns:
        Consolidated result dictionary
    """
    # If too many pages, split into batches
    if len(page_results) > 8:
        print(f"Splitting consolidation into batches due to {len(page_results)} pages")
        return await consolidate_results_in_batches(page_results, sheet_type)
    
    page_results_json = json.dumps(page_results, ensure_ascii=False, indent=2)
    
    # Use appropriate schema and prompt based on sheet type
    if sheet_type == "civil":
        consolidation_prompt = format_civil_consolidation_prompt(page_results_json, CIVIL_FINAL_SCHEMA)
        schema = CIVIL_FINAL_SCHEMA
    else:
        consolidation_prompt = format_consolidation_prompt(page_results_json, FINAL_SCHEMA)
        schema = FINAL_SCHEMA
    
    # Higher base limit with single retry
    base_tokens = 32768
    retry_tokens = 65536
    
    for attempt, max_tokens in enumerate([base_tokens, retry_tokens]):
        try:
            final_response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": consolidation_prompt
                    }
                ],
                max_completion_tokens=max_tokens
            )
            
            finish_reason = final_response.choices[0].finish_reason
            final_text = final_response.choices[0].message.content.strip()
            final_result = parse_llm_json(final_text)
            
            # If response was truncated and this is first attempt, retry once
            if finish_reason == "length" and attempt == 0:
                print(f"Consolidation: Response truncated at {max_tokens} tokens, retrying once...")
                continue
            
            # Check if result has error from incomplete JSON and retry once
            if "error" in final_result and final_result.get("error") == "Invalid JSON returned" and attempt == 0:
                print(f"Consolidation: Invalid JSON (possibly truncated), retrying once...")
                continue
            
            return final_result
            
        except Exception as e:
            print(f"Consolidation error at {max_tokens} tokens: {str(e)}")
            if attempt == 1:  # Last attempt
                return {"error": str(e)}
            continue
    
    # If retry failed, return with warning
    return {"error": "Failed to consolidate results after retry with higher token limit"}


async def consolidate_results_in_batches(page_results: list, sheet_type: str = "architectural") -> Dict[str, Any]:
    """
    Consolidate results by splitting into batches when document is too large
    
    Args:
        page_results: List of page analysis results
        sheet_type: Type of drawing ("architectural", "civil", "structural")
    
    Returns:
        Consolidated result dictionary
    """
    batch_size = 4  # Process 4 pages at a time
    batches = [page_results[i:i + batch_size] for i in range(0, len(page_results), batch_size)]
    
    batch_results = []
    for i, batch in enumerate(batches):
        print(f"Processing batch {i + 1}/{len(batches)} with {len(batch)} pages")
        batch_result = await consolidate_single_batch(batch, sheet_type)
        batch_results.append(batch_result)
    
    # Merge batch results
    return await merge_batch_results(batch_results, sheet_type)


async def consolidate_single_batch(page_results: list, sheet_type: str = "architectural") -> Dict[str, Any]:
    """
    Consolidate a single batch of page results
    
    Args:
        page_results: List of page analysis results for a batch
        sheet_type: Type of drawing ("architectural", "civil", "structural")
    
    Returns:
        Consolidated result dictionary for the batch
    """
    page_results_json = json.dumps(page_results, ensure_ascii=False, indent=2)
    
    # Use appropriate schema and prompt based on sheet type
    if sheet_type == "civil":
        consolidation_prompt = format_civil_consolidation_prompt(page_results_json, CIVIL_FINAL_SCHEMA)
        schema = CIVIL_FINAL_SCHEMA
    else:
        consolidation_prompt = format_consolidation_prompt(page_results_json, FINAL_SCHEMA)
        schema = FINAL_SCHEMA
    
    try:
        final_response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": consolidation_prompt
                }
            ],
            max_completion_tokens=32768
        )
        
        final_text = final_response.choices[0].message.content.strip()
        return parse_llm_json(final_text)
        
    except Exception as e:
        return {"error": f"Batch consolidation failed: {str(e)}"}


async def merge_batch_results(batch_results: list, sheet_type: str = "architectural") -> Dict[str, Any]:
    """
    Merge results from multiple batches into final consolidated result
    
    Args:
        batch_results: List of batch consolidation results
        sheet_type: Type of drawing ("architectural", "civil", "structural")
    
    Returns:
        Final merged result dictionary
    """
    # Use appropriate schema based on sheet type
    schema = CIVIL_FINAL_SCHEMA if sheet_type == "civil" else FINAL_SCHEMA
    merged = json.loads(schema)
    
    # Define element keys based on sheet type
    if sheet_type == "civil":
        element_keys = ["stations", "match_lines", "curb_gutter", "pedestrian_ramps", 
                       "right_of_way", "work_limits", "hatched_areas", "annotations", "notes"]
    else:
        element_keys = ["rooms", "walls", "doors", "windows", "dimensions", "annotations"]
    
    for batch_result in batch_results:
        if "error" in batch_result:
            continue
        
        # Merge lists of elements
        for key in element_keys:
            if key in batch_result and isinstance(batch_result[key], list):
                if key not in merged:
                    merged[key] = []
                merged[key].extend(batch_result[key])
    
    merged["status"] = "completed"
    merged["message"] = f"Consolidated from {len(batch_results)} batches"
    
    return merged
