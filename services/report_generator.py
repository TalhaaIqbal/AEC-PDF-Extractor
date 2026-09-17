"""
Report Generator Service
Handles generation of human-readable markdown reports
"""
import json
from typing import Dict, Any
from openai import AsyncOpenAI
from config.settings import MODEL, OPENAI_API_KEY
from prompts import load_report_generation_prompt

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)
REPORT_SYSTEM_PROMPT = load_report_generation_prompt()


def build_no_data_report(result: Dict[str, Any]) -> str:
    """
    Build a report when no data was extracted
    
    Args:
        result: Result dictionary with status and message
    
    Returns:
        Markdown report string
    """
    status = result.get("status", "unknown")
    message = result.get("message", "No AEC information was extracted from this document.")

    return f"""# AEC Drawing Report

## Extraction Status: `{status}`

{message}

No element counts, rooms, walls, doors, dimensions, or annotations
were available to report on. This is **not** a statement that the
physical drawing contains none of these things - it means the
upstream extraction stages did not detect or capture any AEC
content for this file.

## Data Gaps / Extraction Limitations

|| Category | Status | Explanation |
||---|---|---|
|| All AEC elements | 0 extracted | {message} |

## Suggested Next Steps

- Confirm the correct PDF was uploaded.
- Re-run the pipeline on a higher-resolution scan if the source
  was a low-quality raster image.
- Check that the file contains actual drawing pages rather than
  only cover sheets, blank pages, or non-drawing content.
"""


async def generate_markdown_report(final_result: Dict[str, Any]) -> str:
    """
    Generate human-readable markdown report using LLM with single retry for truncated responses
    
    Args:
        final_result: Final consolidated AEC extraction result
    
    Returns:
        Markdown report string
    """
    
    try:
        # Higher base limit with single retry
        base_tokens = 32768
        retry_tokens = 65536
        
        for attempt, max_tokens in enumerate([base_tokens, retry_tokens]):
            report_response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": REPORT_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": (
                            "Convert the following extracted AEC drawing "
                            "JSON into the required long human-readable "
                            "Markdown report.\n\n"
                            "AEC JSON:\n"
                            + json.dumps(final_result, indent=2, ensure_ascii=False)
                        )
                    }
                ],
                max_completion_tokens=max_tokens
            )
            
            finish_reason = report_response.choices[0].finish_reason
            report_text = report_response.choices[0].message.content.strip()
            
            # If response was truncated and this is first attempt, retry once
            if finish_reason == "length" and attempt == 0:
                print(f"Report generation: Response truncated at {max_tokens} tokens, retrying once...")
                continue
            
            return report_text
        
        # If retry failed, return with warning
        return report_text + "\n\n[WARNING: Report may be truncated due to length limits]"
    
    except Exception as e:
        return f"# Error Generating Report\n\nFailed to generate report: {str(e)}"
