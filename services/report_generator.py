"""
Report Generator Service
Handles generation of human-readable markdown reports
"""
import json
from typing import Dict, Any
from openai import AsyncOpenAI
from config.settings import MODEL, OPENAI_API_KEY

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


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
    Generate human-readable markdown report using LLM
    
    Args:
        final_result: Final consolidated AEC extraction result
    
    Returns:
        Markdown report string
    """
    report_system_prompt = """
You are an expert AEC (Architecture, Engineering, Construction)
document analyst and technical report writer.

Your task is to convert the supplied structured AEC JSON into a
LONG, HUMAN-READABLE MARKDOWN REPORT.

The report will be read by normal users such as contractors,
architects, engineers, project managers, building owners, clients.

CRITICAL ACCURACY RULES:
1. USE ONLY INFORMATION PRESENT IN THE SUPPLIED JSON.
2. NEVER invent information.
3. NEVER estimate missing dimensions, areas, quantities.
4. Preserve exact printed values (e.g., 15'-6" stays 15'-6").
5. Clearly distinguish between exact extracted information, 
   information not provided, and uncertain information.
6. If an element has a count of zero, say "0 extracted" rather 
   than "0 physically present".
7. Do not assume missing data means the physical drawing has none.
8. Do not create dimensions from room areas or calculate missing areas.

Create a comprehensive report with these sections:
1. Project / Drawing Overview
2. Overall Element Count
3. Rooms / Spaces
4. Dimensions
5. Wall Information
6. Doors / Windows / Openings
7. Equipment / Fixtures / Building Systems
8. Annotations / Callouts
9. Elevations
10. Materials / Finishes
11. Construction / General Notes
12. Space Relationships
13. Drawing References / Details
14. Important Measurements and Areas Summary
15. Compliance / Life Safety Information
16. Data Gaps / Extraction Limitations
17. Final Human-Readable Summary

Use Markdown tables, headings, bullet points, and bold text for
important values. Make it professional and easy to scan.

Return ONLY the final Markdown report. No JSON, no explanations.
"""
    
    try:
        report_response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": report_system_prompt
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
            max_completion_tokens=16384
        )
        
        return report_response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"# Error Generating Report\n\nFailed to generate report: {str(e)}"
