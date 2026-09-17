"""
AI Analyzer Service
Handles AI-powered analysis using OpenAI API
"""
import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from config.settings import (
    MODEL, OPENAI_API_KEY, SYSTEM_PROMPT, PAGE_JSON_SCHEMA, FINAL_SCHEMA,
    SCHEMAS, SYSTEM_PROMPTS, DEFAULT_SHEET_TYPE
)
from utils.helpers import compact_json, image_to_data_url, parse_llm_json

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def detect_sheet_type(vector_data: Optional[Dict[str, Any]]) -> str:
    """
    Detect sheet type from title block and content
    
    Args:
        vector_data: Optional vector data for the page
    
    Returns:
        Detected sheet type ('civil' or 'architectural')
    """
    if not vector_data:
        return DEFAULT_SHEET_TYPE
    
    texts = vector_data.get("texts", [])
    text_content = " ".join([t.get("text", "").lower() for t in texts])
    
    # Civil engineering keywords
    civil_keywords = [
        "roadway", "site", "grading", "utility", "civil", "drainage", 
        "paving", "curb", "gutter", "station", "offset", "r/w", 
        "right of way", "match line", "centerline", "slope"
    ]
    
    # Architectural keywords
    architectural_keywords = [
        "floor plan", "elevation", "section", "detail", "architectural",
        "room", "wall", "door", "window", "stairs", "ceiling"
    ]
    
    # Check for civil keywords
    civil_score = sum(1 for keyword in civil_keywords if keyword in text_content)
    architectural_score = sum(1 for keyword in architectural_keywords if keyword in text_content)
    
    if civil_score > architectural_score:
        return "civil"
    elif architectural_score > civil_score:
        return "architectural"
    
    # Check path types if available
    if "paths" in vector_data and isinstance(vector_data["paths"], dict):
        path_types = vector_data["paths"].get("path_types", {})
        if path_types.get("hatch", 0) > 10:  # Significant hatching suggests civil
            return "civil"
    
    return DEFAULT_SHEET_TYPE


def build_page_prompt(page_index: int, vector_data: Optional[Dict[str, Any]], sheet_type: str = DEFAULT_SHEET_TYPE) -> str:
    """
    Build prompt for page analysis
    
    Args:
        page_index: Index of the page being analyzed
        vector_data: Optional vector data for the page
        sheet_type: Type of sheet ('civil' or 'architectural')
    
    Returns:
        Formatted prompt string
    """
    # Get appropriate schema and prompt for sheet type
    schema = SCHEMAS.get(sheet_type, SCHEMAS[DEFAULT_SHEET_TYPE])
    system_prompt = SYSTEM_PROMPTS.get(sheet_type, SYSTEM_PROMPTS[DEFAULT_SHEET_TYPE])
    
    vector_text = compact_json(vector_data, max_chars=25000)

    prompt = f"""
Analyze AEC drawing page {page_index + 1}.

The page image (attached) is the PRIMARY evidence.

Optional native PDF text/vector evidence for this page:

===== VECTOR DATA =====
{vector_text if vector_text else "Not available - this page has no native vector data (likely a scanned/raster page)."}
===== END VECTOR DATA =====

Note: Vector data includes exact text spans (prioritize for text content) and a summary of path geometry. Use text spans for accurate names, dimensions, and annotations. Use the image for spatial relationships and geometry.

Extract only important, reliable AEC information visible on or
supported by this page. If nothing meaningful is detectable,
return the schema with empty lists and "detection_status":
"no_elements_detected".

Return JSON using this exact structure:

{schema}
"""
    return prompt


async def analyze_page(page_index: int, page_image_path: str, vector_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze a single page using LLM
    
    Args:
        page_index: Index of the page to analyze
        page_image_path: Path to the page image
        vector_data: Optional vector data for the page
    
    Returns:
        Analysis result dictionary
    """
    # Detect sheet type
    sheet_type = detect_sheet_type(vector_data)
    
    # Get appropriate system prompt for sheet type
    system_prompt = SYSTEM_PROMPTS.get(sheet_type, SYSTEM_PROMPTS[DEFAULT_SHEET_TYPE])
    
    image_url = image_to_data_url(page_image_path)
    prompt = build_page_prompt(page_index, vector_data, sheet_type)

    max_tokens = 4096
    for attempt in range(2):  # Try twice, doubling limit on retry
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
        
        if finish_reason == "length" and attempt == 0:
            print(f"Warning: Page {page_index + 1} response truncated at {max_tokens} tokens. Retrying with higher limit...")
            max_tokens = 8192  # Double the limit for retry
            continue
        
        if finish_reason == "length":
            print(f"Warning: Page {page_index + 1} response still truncated even at {max_tokens} tokens. JSON may be incomplete.")
        
        result = parse_llm_json(text, page_index)
        # Add sheet type to result for tracking
        result["sheet_type"] = sheet_type
        return result

    # Fallback if both attempts fail
    result = parse_llm_json(text, page_index)
    result["sheet_type"] = sheet_type
    return result


async def consolidate_results(page_results: list) -> Dict[str, Any]:
    """
    Consolidate results from multiple pages using AI
    
    Args:
        page_results: List of page analysis results
    
    Returns:
        Consolidated result dictionary
    """
    # Filter out pages with no elements detected
    meaningful_results = [r for r in page_results if r.get("detection_status") != "no_elements_detected"]
    
    if not meaningful_results:
        # Return empty final schema
        return json.loads(FINAL_SCHEMA)
    
    # Check for mixed sheet types
    sheet_types = set(r.get("sheet_type", DEFAULT_SHEET_TYPE) for r in meaningful_results)
    
    # If mixed types, separate and consolidate separately
    if len(sheet_types) > 1:
        print(f"Mixed sheet types detected: {sheet_types}. Separating consolidation...")
        return await consolidate_mixed_types(meaningful_results, sheet_types)
    
    # If too many pages, split into batches and consolidate hierarchically
    if len(meaningful_results) > 8:  # Threshold for batch processing
        print(f"Large document ({len(meaningful_results)} pages). Using batch consolidation...")
        return await consolidate_in_batches(meaningful_results)
    
    # Determine consolidation approach based on sheet type
    primary_sheet_type = meaningful_results[0].get("sheet_type", DEFAULT_SHEET_TYPE)
    
    if primary_sheet_type == "civil":
        return await consolidate_civil_results(meaningful_results)
    else:
        return await consolidate_architectural_results(meaningful_results)
    
    try:
        max_tokens = 8192
        for attempt in range(2):  # Try twice, doubling limit on retry
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
            
            if finish_reason == "length" and attempt == 0:
                print(f"Warning: Consolidation response truncated at {max_tokens} tokens. Retrying with higher limit...")
                max_tokens = 16384  # Double the limit for retry
                continue
            
            if finish_reason == "length":
                print(f"Warning: Consolidation response still truncated even at {max_tokens} tokens. JSON may be incomplete.")
            
            final_result = parse_llm_json(final_text)
            return final_result
        
        # Fallback if both attempts fail
        final_result = parse_llm_json(final_text)
        
    except Exception as e:
        final_result = {"error": str(e)}
    
    return final_result


async def consolidate_in_batches(page_results: list) -> Dict[str, Any]:
    """
    Consolidate results in batches for large documents
    
    Args:
        page_results: List of page analysis results
    
    Returns:
        Consolidated result dictionary
    """
    # Determine primary sheet type
    primary_sheet_type = page_results[0].get("sheet_type", DEFAULT_SHEET_TYPE)
    system_prompt = SYSTEM_PROMPTS.get(primary_sheet_type, SYSTEM_PROMPTS[DEFAULT_SHEET_TYPE])
    
    batch_size = 4  # Process 4 pages at a time
    batches = [page_results[i:i + batch_size] for i in range(0, len(page_results), batch_size)]
    
    batch_results = []
    for i, batch in enumerate(batches):
        print(f"Processing batch {i + 1}/{len(batches)} ({len(batch)} pages)...")
        
        if primary_sheet_type == "civil":
            batch_prompt = f"""
You are consolidating civil engineering information extracted from multiple pages
of the SAME roadway/site/civil document.

Rules:
- Keep only meaningful civil engineering information.
- Remove duplicates; merge repeated stations, match lines, curb/gutter sections
  when they clearly refer to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- If two values conflict and it cannot be resolved, preserve the
  uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

PAGE RESULTS:

{json.dumps(batch, ensure_ascii=False, indent=2)}
"""
        else:
            batch_prompt = f"""
You are consolidating AEC information extracted from multiple pages
of the SAME architectural/engineering/construction document.

Rules:
- Keep only meaningful AEC information.
- Remove duplicates; merge repeated rooms/walls/doors/windows/levels
  /grids/dimensions/annotations/references when they clearly refer
  to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- If two values conflict and it cannot be resolved, preserve the
  uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

PAGE RESULTS:

{json.dumps(batch, ensure_ascii=False, indent=2)}
"""
        
        try:
            max_tokens = 8192
            for attempt in range(2):
                batch_response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": batch_prompt
                        }
                    ],
                    max_completion_tokens=max_tokens
                )
                
                finish_reason = batch_response.choices[0].finish_reason
                batch_text = batch_response.choices[0].message.content.strip()
                
                if finish_reason == "length" and attempt == 0:
                    print(f"Batch {i + 1} truncated at {max_tokens} tokens. Retrying...")
                    max_tokens = 16384
                    continue
                
                if finish_reason == "length":
                    print(f"Batch {i + 1} still truncated even at {max_tokens} tokens.")
                
                batch_result = parse_llm_json(batch_text)
                batch_results.append(batch_result)
                break
                
        except Exception as e:
            print(f"Error processing batch {i + 1}: {e}")
            batch_results.append({"error": str(e), "batch_index": i})
    
    # Now consolidate the batch results
    print(f"Consolidating {len(batch_results)} batch results...")
    final_consolidation_prompt = f"""
You are consolidating AEC information from batch processing of a large document.

Rules:
- Keep only meaningful AEC information.
- Remove duplicates; merge repeated rooms/walls/doors/windows/levels
  /grids/dimensions/annotations/references when they clearly refer
  to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- If two values conflict and it cannot be resolved, preserve the
  uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

BATCH RESULTS:

{json.dumps(batch_results, ensure_ascii=False, indent=2)}
"""
    
    try:
        max_tokens = 16384
        for attempt in range(2):
            final_response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": final_consolidation_prompt
                    }
                ],
                max_completion_tokens=max_tokens
            )
            
            finish_reason = final_response.choices[0].finish_reason
            final_text = final_response.choices[0].message.content.strip()
            
            if finish_reason == "length" and attempt == 0:
                print(f"Final consolidation truncated at {max_tokens} tokens. Retrying...")
                max_tokens = 32768
                continue
            
            if finish_reason == "length":
                print(f"Final consolidation still truncated even at {max_tokens} tokens.")
            
            final_result = parse_llm_json(final_text)
            return final_result
        
        final_result = parse_llm_json(final_text)
        
    except Exception as e:
        final_result = {"error": str(e)}
    
    return final_result


async def consolidate_architectural_results(page_results: list) -> Dict[str, Any]:
    """
    Consolidate architectural results using AI
    
    Args:
        page_results: List of page analysis results
    
    Returns:
        Consolidated result dictionary
    """
    consolidation_prompt = f"""
You are consolidating AEC information extracted from multiple pages
of the SAME architectural/engineering/construction document.

Rules:
- Keep only meaningful AEC information.
- Remove duplicates; merge repeated rooms/walls/doors/windows/levels
  /grids/dimensions/annotations/references when they clearly refer
  to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- Skip pages with "detection_status": "no_elements_detected" -
  they contributed nothing.
- If two values conflict and it cannot be resolved, preserve the
  uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

PAGE RESULTS:

{json.dumps(page_results, ensure_ascii=False, indent=2)}
"""
    
    try:
        max_tokens = 8192
        for attempt in range(2):  # Try twice, doubling limit on retry
            final_response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPTS["architectural"]
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
            
            if finish_reason == "length" and attempt == 0:
                print(f"Warning: Consolidation response truncated at {max_tokens} tokens. Retrying with higher limit...")
                max_tokens = 16384  # Double the limit for retry
                continue
            
            if finish_reason == "length":
                print(f"Warning: Consolidation response still truncated even at {max_tokens} tokens. JSON may be incomplete.")
            
            final_result = parse_llm_json(final_text)
            return final_result
        
        # Fallback if both attempts fail
        final_result = parse_llm_json(final_text)
        
    except Exception as e:
        final_result = {"error": str(e)}
    
    return final_result


async def consolidate_civil_results(page_results: list) -> Dict[str, Any]:
    """
    Consolidate civil engineering results using AI
    
    Args:
        page_results: List of page analysis results
    
    Returns:
        Consolidated result dictionary
    """
    consolidation_prompt = f"""
You are consolidating civil engineering information extracted from multiple pages
of the SAME roadway/site/civil document.

Rules:
- Keep only meaningful civil engineering information.
- Remove duplicates; merge repeated stations, match lines, curb/gutter sections
  when they clearly refer to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- Skip pages with "detection_status": "no_elements_detected" -
  they contributed nothing.
- If two values conflict and it cannot be resolved, preserve the
  uncertainty rather than inventing an answer.
- Validate that stations fall within match line ranges when provided.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

PAGE RESULTS:

{json.dumps(page_results, ensure_ascii=False, indent=2)}
"""
    
    try:
        max_tokens = 8192
        for attempt in range(2):  # Try twice, doubling limit on retry
            final_response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPTS["civil"]
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
            
            if finish_reason == "length" and attempt == 0:
                print(f"Warning: Civil consolidation response truncated at {max_tokens} tokens. Retrying with higher limit...")
                max_tokens = 16384  # Double the limit for retry
                continue
            
            if finish_reason == "length":
                print(f"Warning: Civil consolidation response still truncated even at {max_tokens} tokens. JSON may be incomplete.")
            
            final_result = parse_llm_json(final_text)
            return final_result
        
        # Fallback if both attempts fail
        final_result = parse_llm_json(final_text)
        
    except Exception as e:
        final_result = {"error": str(e)}
    
    return final_result


async def consolidate_mixed_types(page_results: list, sheet_types: set) -> Dict[str, Any]:
    """
    Consolidate results from mixed sheet types separately
    
    Args:
        page_results: List of page analysis results
        sheet_types: Set of detected sheet types
    
    Returns:
        Consolidated result dictionary
    """
    consolidated = {"mixed_types": list(sheet_types)}
    
    for sheet_type in sheet_types:
        type_results = [r for r in page_results if r.get("sheet_type") == sheet_type]
        
        if sheet_type == "civil":
            type_consolidated = await consolidate_civil_results(type_results)
        else:
            type_consolidated = await consolidate_architectural_results(type_results)
        
        consolidated[f"{sheet_type}_results"] = type_consolidated
    
    # Create a unified final result
    unified = json.loads(FINAL_SCHEMA)
    
    # Merge results from different types
    for sheet_type in sheet_types:
        type_result = consolidated.get(f"{sheet_type}_results", {})
        for key in unified.keys():
            if key in type_result and isinstance(type_result[key], list):
                unified[key].extend(type_result[key])
            elif key in type_result and type_result[key] is not None:
                unified[key] = type_result[key]
    
    unified["sheet_types"] = list(sheet_types)
    return unified
