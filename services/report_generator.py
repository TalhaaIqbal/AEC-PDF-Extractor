"""
Report Generator Service
Handles generation of human-readable markdown reports
"""
import json
from typing import Dict, Any
from pathlib import Path
from openai import AsyncOpenAI
from config.settings import MODEL, OPENAI_API_KEY


def load_prompt_file(filename: str) -> str:
    """Load prompt content from prompts directory"""
    # Get the project root (parent of services directory)
    project_root = Path(__file__).parent.parent
    prompt_path = project_root / "prompts" / filename
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Prompt file not found: {prompt_path}")

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def compute_element_counts(final_result: Dict[str, Any]) -> Dict[str, int]:
    """
    Compute accurate element counts from the JSON data
    
    Args:
        final_result: Final consolidated AEC extraction result
    
    Returns:
        Dictionary with element counts
    """
    counts = {}
    
    # Common element types
    element_types = [
        "levels", "grids", "rooms", "walls", "doors", "windows", 
        "columns", "stairs", "dimensions", "elevations", "annotations",
        "materials", "notes", "relationships", "references"
    ]
    
    # Civil-specific element types
    civil_types = ["stations", "match_lines", "curb_gutter", "ramps", 
                   "right_of_way", "work_limits", "hatched_areas"]
    
    # Determine which types to count based on sheet type
    sheet_type = final_result.get("sheet_type", "architectural")
    if sheet_type == "civil":
        element_types.extend(civil_types)
    
    # Count each element type
    for element_type in element_types:
        elements = final_result.get(element_type, [])
        if isinstance(elements, list):
            counts[element_type] = len(elements)
        else:
            counts[element_type] = 0
    
    # Count sheets
    sheets = final_result.get("sheets", [])
    counts["sheets"] = len(sheets) if isinstance(sheets, list) else 0
    
    # Total count
    counts["total_elements"] = sum(counts.values())
    
    return counts


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
    
    # Compute element counts even for no-data reports
    element_counts = compute_element_counts(result)

    report = f"""# AEC Drawing Report

## Extraction Status: `{status}`

{message}

## ACCURATE ELEMENT COUNTS (COMPUTED FROM JSON)

| Element Type | Count |
|-------------|-------|
"""
    
    # Add counts to table
    sorted_counts = sorted(element_counts.items(), key=lambda x: x[1], reverse=True)
    for element_type, count in sorted_counts:
        if element_type != "total_elements":
            report += f"| {element_type.replace('_', ' ').title()} | {count} |\n"
    
    report += f"\n**Total Elements: {element_counts['total_elements']}**\n"

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

Element counts shown above are computed from the JSON data. While some element types show 0 extracted, this is **not** a statement that the physical drawing contains none of these things - it means the upstream extraction stages did not detect or capture those AEC elements for this file.

## Data Gaps / Extraction Limitations

||| Category | Status | Explanation |
|||---|---|---|
||| All AEC elements | 0 extracted | """ + message + """ |
"""

    if error_pages:
        report += f"| Page processing errors | {error_page_count} pages | {len(error_pages)} pages failed to process: {', '.join(map(str, error_pages))} |\n"

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
    # Detect sheet type from result
    sheet_type = final_result.get("sheet_type", "architectural")
    
    if sheet_type == "civil":
        report_system_prompt = load_prompt_file("classes/civil/civil_report_prompt.txt")
        print(f"Report generation: Using prompt 'classes/civil/civil_report_prompt.txt' for sheet type '{sheet_type}'")
    else:
        report_system_prompt = load_prompt_file("classes/architectural/architectural_report_prompt.txt")
        print(f"Report generation: Using prompt 'classes/architectural/architectural_report_prompt.txt' for sheet type '{sheet_type}'")
    
    # Compute accurate element counts in code
    element_counts = compute_element_counts(final_result)
    
    # Create a summary table with accurate counts
    count_summary = "## ACCURATE ELEMENT COUNTS (COMPUTED FROM JSON)\n\n"
    count_summary += "| Element Type | Count |\n"
    count_summary += "|-------------|-------|\n"
    
    # Sort by count (descending) for better readability
    sorted_counts = sorted(element_counts.items(), key=lambda x: x[1], reverse=True)
    for element_type, count in sorted_counts:
        if element_type != "total_elements":  # Skip total in the table
            count_summary += f"| {element_type.replace('_', ' ').title()} | {count} |\n"
    
    count_summary += f"\n**Total Elements: {element_counts['total_elements']}**\n"
    
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
                        f"Convert the following extracted AEC drawing "
                        f"JSON into the required long human-readable "
                        f"Markdown report. The detected sheet type is: {sheet_type.upper()}.\n\n"
                        f"IMPORTANT: Use these EXACT element counts in your report - do not recalculate them:\n\n"
                        f"{count_summary}\n\n"
                        "AEC JSON:\n"
                        + json.dumps(final_result, indent=2, ensure_ascii=False)
                    )
                }
            ],
            max_completion_tokens=16384
        )

        content = report_response.choices[0].message.content.strip()
        return content

    except Exception as e:
        return f"# Error Generating Report\n\nFailed to generate report: {str(e)}"
