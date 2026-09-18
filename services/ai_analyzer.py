"""
AI Analyzer Service
Handles AI-powered analysis using OpenAI API
"""
import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from config.settings import (
    MODEL, OPENAI_API_KEY, SYSTEM_PROMPT, PAGE_JSON_SCHEMA, FINAL_SCHEMA,
    SCHEMAS, SYSTEM_PROMPTS, DEFAULT_SHEET_TYPE, UNIVERSAL_SYSTEM_PROMPT, UNIVERSAL_PAGE_JSON_SCHEMA,
    REGION_DETECTION_PROMPT, REGION_DETECTION_SCHEMA, CROP_ANALYSIS_CONTEXT,
    REGION_CROP_DPI, REGION_ENHANCEMENT_METHOD, MIN_REGION_SIZE, MAX_REGIONS_PER_PAGE, MIN_REGION_CONFIDENCE
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


def build_page_prompt(page_index: int, vector_data: Optional[Dict[str, Any]], sheet_type: str = DEFAULT_SHEET_TYPE, schema: str = None) -> str:
    """
    Build prompt for page analysis
    
    Args:
        page_index: Index of the page being analyzed
        vector_data: Optional vector data for the page
        sheet_type: Type of sheet ('civil' or 'architectural')
        schema: Optional schema string (if None, will be determined from sheet_type)
    
    Returns:
        Formatted prompt string
    """
    # Get appropriate schema if not provided
    if schema is None:
        schema = SCHEMAS.get(sheet_type, SCHEMAS[DEFAULT_SHEET_TYPE])
    
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
    # Use universal approach - AI detects sheet type from image itself
    # This works for both vector and raster/scanned pages
    system_prompt = UNIVERSAL_SYSTEM_PROMPT
    schema = UNIVERSAL_PAGE_JSON_SCHEMA
    print(f"Page {page_index + 1}: Using prompt 'universal_system_prompt.txt' and schema 'universal_schema.json'")
    
    image_url = image_to_data_url(page_image_path)
    prompt = build_page_prompt(page_index, vector_data, "universal", schema)

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
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                ]
            }
        ],
        max_completion_tokens=16384
    )

    text = response.choices[0].message.content.strip()
    result = parse_llm_json(text, page_index)
    # Use the sheet_type detected by AI (if present), otherwise use detected type
    detected_sheet_type = result.get("sheet_type", detect_sheet_type(vector_data))
    result["sheet_type"] = detected_sheet_type
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
    
    # Use universal consolidation for all types since universal schema supports both
    return await consolidate_universal_results(meaningful_results, primary_sheet_type)


async def consolidate_universal_results(page_results: list, sheet_type: str) -> Dict[str, Any]:
    """
    Consolidate results using universal approach that handles both civil and architectural
    
    Args:
        page_results: List of page analysis results
        sheet_type: Primary sheet type detected
    
    Returns:
        Consolidated result dictionary
    """
    # Use the appropriate system prompt based on detected sheet type
    system_prompt = SYSTEM_PROMPTS.get(sheet_type, UNIVERSAL_SYSTEM_PROMPT)
    prompt_name = f"{sheet_type}_system_prompt.txt" if sheet_type in SYSTEM_PROMPTS else "universal_system_prompt.txt"
    print(f"Consolidation: Using prompt '{prompt_name}' for sheet type '{sheet_type}'")
    
    consolidation_prompt = f"""
You are consolidating AEC information extracted from multiple pages
of the SAME document.

Primary sheet type detected: {sheet_type.upper()}

Rules:
- Keep only meaningful AEC information appropriate to the sheet type.
- Remove duplicates; merge repeated elements when they clearly refer to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- Skip pages with "detection_status": "no_elements_detected" - they contributed nothing.
- If two values conflict and it cannot be resolved, preserve the uncertainty rather than inventing an answer.
- For civil sheets: validate that stations fall within match line ranges when provided.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

PAGE RESULTS:

{json.dumps(page_results, ensure_ascii=False, indent=2)}
"""
    
    try:
        final_response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": consolidation_prompt
                }
            ],
            max_completion_tokens=32768
        )

        final_text = final_response.choices[0].message.content.strip()
        final_result = parse_llm_json(final_text)
        final_result["sheet_type"] = sheet_type
        return final_result

    except Exception as e:
        final_result = {"error": str(e), "sheet_type": sheet_type}

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
    system_prompt = SYSTEM_PROMPTS.get(primary_sheet_type, UNIVERSAL_SYSTEM_PROMPT)
    prompt_name = f"{primary_sheet_type}_system_prompt.txt" if primary_sheet_type in SYSTEM_PROMPTS else "universal_system_prompt.txt"
    print(f"Batch consolidation: Using prompt '{prompt_name}' for sheet type '{primary_sheet_type}'")
    
    batch_size = 4  # Process 4 pages at a time
    batches = [page_results[i:i + batch_size] for i in range(0, len(page_results), batch_size)]
    
    batch_results = []
    for i, batch in enumerate(batches):
        print(f"Processing batch {i + 1}/{len(batches)} ({len(batch)} pages)...")
        
        batch_prompt = f"""
You are consolidating AEC information extracted from multiple pages
of the SAME document.

Primary sheet type: {primary_sheet_type.upper()}

Rules:
- Keep only meaningful AEC information appropriate to the sheet type.
- Remove duplicates; merge repeated elements when they clearly refer to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- If two values conflict and it cannot be resolved, preserve the uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

PAGE RESULTS:

{json.dumps(batch, ensure_ascii=False, indent=2)}
"""
        
        try:
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
                max_completion_tokens=32768
            )

            batch_text = batch_response.choices[0].message.content.strip()
            batch_result = parse_llm_json(batch_text)
            batch_results.append(batch_result)

        except Exception as e:
            print(f"Error processing batch {i + 1}: {e}")
            batch_results.append({"error": str(e), "batch_index": i})
    
    # Now consolidate the batch results
    print(f"Consolidating {len(batch_results)} batch results...")
    final_consolidation_prompt = f"""
You are consolidating AEC information from batch processing of a large document.

Primary sheet type: {primary_sheet_type.upper()}

Rules:
- Keep only meaningful AEC information appropriate to the sheet type.
- Remove duplicates; merge repeated elements when they clearly refer to the same entity.
- Preserve page references where useful.
- Do not invent missing information.
- If two values conflict and it cannot be resolved, preserve the uncertainty rather than inventing an answer.

Return ONLY valid JSON using this structure:

{FINAL_SCHEMA}

BATCH RESULTS:

{json.dumps(batch_results, ensure_ascii=False, indent=2)}
"""
    
    try:
        final_response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": final_consolidation_prompt
                }
            ],
            max_completion_tokens=65536
        )

        final_text = final_response.choices[0].message.content.strip()
        final_result = parse_llm_json(final_text)
        final_result["sheet_type"] = primary_sheet_type
        return final_result

    except Exception as e:
        final_result = {"error": str(e), "sheet_type": primary_sheet_type}

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
        type_consolidated = await consolidate_universal_results(type_results, sheet_type)
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


async def detect_regions(page_index: int, page_image_path: str, vector_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect regions of interest on a page for closer inspection
    
    Args:
        page_index: Index of the page to analyze
        page_image_path: Path to the page image
        vector_data: Optional vector data for the page
    
    Returns:
        Region detection result dictionary
    """
    image_url = image_to_data_url(page_image_path)
    
    # Build region detection prompt
    vector_text = compact_json(vector_data, max_chars=25000)
    
    region_prompt = f"""
Analyze AEC drawing page {page_index + 1} to identify regions requiring closer inspection.

The page image (attached) is the PRIMARY evidence.

Optional native PDF text/vector evidence for this page:

===== VECTOR DATA =====
{vector_text if vector_text else "Not available - this page has no native vector data (likely a scanned/raster page)."}
===== END VECTOR DATA =====

Identify regions that contain significant AEC information that would benefit from detailed crop-based analysis.

Return JSON using this exact structure:

{REGION_DETECTION_SCHEMA}
"""
    
    print(f"Page {page_index + 1}: Detecting regions using 'region_detection_system_prompt.txt'")
    
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": REGION_DETECTION_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": region_prompt},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                ]
            }
        ],
        max_completion_tokens=4096
    )
    
    text = response.choices[0].message.content.strip()
    result = parse_llm_json(text, page_index)
    
    # Filter regions based on confidence and size
    if "regions" in result:
        filtered_regions = []
        for region in result["regions"]:
            # Check confidence level
            region_confidence = region.get("confidence", "low")
            if MIN_REGION_CONFIDENCE == "high" and region_confidence != "high":
                continue
            elif MIN_REGION_CONFIDENCE == "medium" and region_confidence == "low":
                continue
            
            # Check region size (minimum 5% of page area)
            bbox = region.get("bbox", {})
            area = bbox.get("width", 0) * bbox.get("height", 0)
            if area < 0.05:  # Less than 5% of page area
                continue
            
            filtered_regions.append(region)
        
        # Limit number of regions
        filtered_regions = filtered_regions[:MAX_REGIONS_PER_PAGE]
        result["regions"] = filtered_regions
        
        # Update requires_close_inspection based on filtered regions
        result["requires_close_inspection"] = len(filtered_regions) > 0
    
    return result


async def analyze_crop(crop_image_path: str, region_metadata: Dict[str, Any], sheet_type: str) -> Dict[str, Any]:
    """
    Analyze a cropped region in detail
    
    Args:
        crop_image_path: Path to the enhanced crop image
        region_metadata: Region information including type, bbox, expected elements
        sheet_type: Detected sheet type (civil or architectural)
    
    Returns:
        Detailed analysis result for the crop
    """
    image_url = image_to_data_url(crop_image_path)
    
    # Build crop-specific context
    region_type = region_metadata.get("region_type", "unknown")
    bbox = region_metadata.get("bbox", {})
    priority = region_metadata.get("priority", "medium")
    expected_elements = region_metadata.get("expected_elements", [])
    
    bbox_description = f"x={bbox.get('x', 0):.2f}, y={bbox.get('y', 0):.2f}, w={bbox.get('width', 0):.2f}, h={bbox.get('height', 0):.2f}"
    
    crop_context = CROP_ANALYSIS_CONTEXT.format(
        region_type=region_type,
        bbox_description=bbox_description,
        priority=priority,
        expected_elements=", ".join(expected_elements) if expected_elements else "various AEC elements",
        sheet_type=sheet_type
    )
    
    # Use universal schema for crop analysis
    schema = UNIVERSAL_PAGE_JSON_SCHEMA
    
    crop_prompt = f"""
{crop_context}

Analyze this cropped region from an AEC drawing.

Return JSON using this exact structure:

{schema}
"""
    
    region_id = region_metadata.get("region_id", "unknown")
    print(f"Analyzing crop '{region_id}' (type: {region_type}, priority: {priority})")
    
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": UNIVERSAL_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": crop_prompt},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                ]
            }
        ],
        max_completion_tokens=16384
    )
    
    text = response.choices[0].message.content.strip()
    result = parse_llm_json(text)
    
    # Add region metadata to result
    result["region_id"] = region_id
    result["region_type"] = region_type
    result["crop_metadata"] = region_metadata
    
    return result
