"""
AI Analyzer Service
Handles AI-powered analysis using OpenAI API
"""
import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from config.settings import MODEL, OPENAI_API_KEY, SYSTEM_PROMPT, PAGE_JSON_SCHEMA, FINAL_SCHEMA
from utils.helpers import compact_json, image_to_data_url, parse_llm_json

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def build_page_prompt(page_index: int, vector_data: Optional[Dict[str, Any]]) -> str:
    """
    Build prompt for page analysis
    
    Args:
        page_index: Index of the page being analyzed
        vector_data: Optional vector data for the page
    
    Returns:
        Formatted prompt string
    """
    vector_text = compact_json(vector_data, max_chars=30000)

    prompt = f"""
Analyze AEC drawing page {page_index + 1}.

The page image (attached) is the PRIMARY evidence.

Optional native PDF text/vector evidence for this page:

===== VECTOR DATA =====
{vector_text if vector_text else "Not available - this page has no native vector data (likely a scanned/raster page)."}
===== END VECTOR DATA =====

Extract only important, reliable AEC information visible on or
supported by this page. If nothing meaningful is detectable,
return the schema with empty lists and "detection_status":
"no_elements_detected".

Return JSON using this exact structure:

{PAGE_JSON_SCHEMA}
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
    image_url = image_to_data_url(page_image_path)
    prompt = build_page_prompt(page_index, vector_data)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        max_completion_tokens=4096
    )

    text = response.choices[0].message.content.strip()
    result = parse_llm_json(text, page_index)

    return result


async def consolidate_results(page_results: list) -> Dict[str, Any]:
    """
    Consolidate results from multiple pages using AI
    
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
            max_completion_tokens=8192
        )
        
        final_text = final_response.choices[0].message.content.strip()
        final_result = parse_llm_json(final_text)
        
    except Exception as e:
        final_result = {"error": str(e)}
    
    return final_result
