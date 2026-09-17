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
    error_pages = result.get("error_pages", [])
    error_page_count = result.get("error_page_count", len(error_pages))
    total_pages = result.get("total_pages", 0)
    successful_pages = result.get("successful_pages", 0)

    report = f"""# AEC Drawing Report

## Extraction Status: `{status}`

{message}
"""

    # Add error page information if available
    if error_pages:
        report += f"""

### Page Processing Errors

{error_page_count} out of {total_pages} pages failed to process:

**Failed pages:** {', '.join(map(str, error_pages))}

These pages encountered errors during analysis and were not included in the final consolidation.
"""

    if status == "consolidation_failed":
        report += f"""

### Consolidation Failure

The merge step failed after successfully processing {successful_pages} pages.
Individual page results are available in the output directory, but a consolidated
model could not be generated.
"""

    report += """

No element counts, rooms, walls, doors, dimensions, or annotations
were available to report on. This is **not** a statement that the
physical drawing contains none of these things - it means the
upstream extraction stages did not detect or capture any AEC
content for this file.

## Data Gaps / Extraction Limitations

||| Category | Status | Explanation |
|||---|---|---|
||| All AEC elements | 0 extracted | """ + message + """ |
"""

    if error_pages:
        report += f"||| Page processing errors | {error_page_count} pages | {len(error_pages)} pages failed to process: {', '.join(map(str, error_pages))} |\n"

    report += """
## Suggested Next Steps

- Confirm the correct PDF was uploaded.
- Re-run the pipeline on a higher-resolution scan if the source
  was a low-quality raster image.
- Check that the file contains actual drawing pages rather than
  only cover sheets, blank pages, or non-drawing content.
"""

    if error_pages:
        report += f"- Review the individual page JSON files for error details (pages: {', '.join(map(str, error_pages))}).\n"

    return report


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
        max_tokens = 16384
        for attempt in range(2):  # Try twice, doubling limit on retry
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
                max_completion_tokens=max_tokens
            )
            
            finish_reason = report_response.choices[0].finish_reason
            content = report_response.choices[0].message.content.strip()
            
            if finish_reason == "length" and attempt == 0:
                print(f"Warning: Report generation truncated at {max_tokens} tokens. Retrying with higher limit...")
                max_tokens = 32768  # Double the limit for retry
                continue
            
            if finish_reason == "length":
                print(f"Warning: Report generation still truncated even at {max_tokens} tokens. Markdown may be incomplete.")
            
            return content
        
        # Fallback if both attempts fail
        return content
    
    except Exception as e:
        return f"# Error Generating Report\n\nFailed to generate report: {str(e)}"
