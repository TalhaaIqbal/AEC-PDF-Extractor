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
    load_final_schema
)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Load prompts and schemas at module level
SYSTEM_PROMPT = load_system_prompt()
PAGE_JSON_SCHEMA = load_page_json_schema()
FINAL_SCHEMA = load_final_schema()


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
    
    if not vector_text:
        vector_text = "Not available - this page has no native vector data (likely a scanned/raster page)."

    return format_page_analysis_prompt(
        page_index=page_index + 1,
        vector_data=vector_text,
        page_json_schema=PAGE_JSON_SCHEMA
    )


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
    page_results_json = json.dumps(page_results, ensure_ascii=False, indent=2)
    consolidation_prompt = format_consolidation_prompt(page_results_json, FINAL_SCHEMA)
    
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
