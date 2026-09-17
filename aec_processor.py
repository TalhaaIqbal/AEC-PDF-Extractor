"""
AEC Processor - Main Pipeline Orchestrator
Coordinates the PDF processing pipeline using modularized services
"""
import os
import json
from typing import Optional, Callable

from config.settings import PDF_DPI, LLM_MAX_IMAGE_DIMENSION
from prompts import load_final_schema, load_civil_final_schema

FINAL_SCHEMA = load_final_schema()
CIVIL_FINAL_SCHEMA = load_civil_final_schema()
from services.pdf_processor import classify_pdf_pages, extract_vector_data, render_page_images
from services.ai_analyzer import analyze_page, consolidate_results, detect_sheet_type, extract_sheet_info_from_vector
from services.report_generator import build_no_data_report, generate_markdown_report
from services.civil_validator import validate_civil_data, validate_civil_consolidation


async def process_pdf(pdf_path: str, output_dir: str, progress_callback: Optional[Callable[[int], None]] = None) -> dict:
    """
    Main PDF processing function - orchestrates the entire pipeline
    
    Args:
        pdf_path: Path to the PDF file to process
        output_dir: Directory to save processing results
        progress_callback: Optional callback function for progress updates
    
    Returns:
        Final consolidated AEC extraction result
    """
    
    # Update progress
    if progress_callback:
        progress_callback(5)
    
    # Stage 1: Classify pages
    page_info = classify_pdf_pages(pdf_path)
    has_pages = len(page_info) > 0
    
    if not has_pages:
        result = {
            "status": "no_images_detected",
            "message": "This PDF has zero pages."
        }
        return result
    
    if progress_callback:
        progress_callback(10)
    
    # Stage 2: Extract vector data for vector pages
    vector_data_by_page = {}
    for p in page_info:
        if p["is_vector"]:
            vector_data_by_page[p["page"]] = extract_vector_data(pdf_path, p["page"])
    
    if progress_callback:
        progress_callback(20)
    
    # Stage 3: Render page images
    page_image_dir = os.path.join(output_dir, "pdf_pages")
    page_images = render_page_images(pdf_path, page_image_dir, PDF_DPI, LLM_MAX_IMAGE_DIMENSION)
    has_page_images = len(page_images) > 0
    
    if not has_page_images:
        result = {
            "status": "no_images_detected",
            "message": "No page images could be rendered."
        }
        return result
    
    if progress_callback:
        progress_callback(30)
    
    # Stage 4: Process each page
    page_results = []
    failed_pages = []
    total_pages = len(page_images)
    
    # Detect sheet type from native PDF text before any AI calls
    sheet_type = "architectural"  # default
    if total_pages > 0:
        try:
            # Extract sheet metadata from native PDF text (vector data)
            first_page_vector = vector_data_by_page.get(0)
            if first_page_vector and "texts" in first_page_vector:
                # Look for sheet title, discipline, drawing type in native text
                sheet_info = extract_sheet_info_from_vector(first_page_vector["texts"])
                sheet_type = detect_sheet_type(sheet_info)
                print(f"Detected sheet type from native text: {sheet_type}")
            else:
                # Fallback: raster image - will use image analysis with architectural first
                print("No native text available, using default architectural schema")
                sheet_type = "architectural"
        except Exception as e:
            print(f"Error detecting sheet type from native text: {str(e)}")
            sheet_type = "architectural"  # fallback
    
    print(f"Processing with sheet type: {sheet_type}")
    print(f"Using schema: {'civil_schema.json' if sheet_type == 'civil' else 'page_json_schema.json'}")
    print(f"Using system prompt: {'civil_system_prompt.md' if sheet_type == 'civil' else 'system_prompt.md'}")
    print(f"Using page analysis prompt: {'civil_page_analysis_prompt.md' if sheet_type == 'civil' else 'page_analysis_prompt.md'}")
    
    # Process all pages with detected sheet type
    for i in range(total_pages):
        image_path = page_images[i]
        vector_data = vector_data_by_page.get(i)
        
        try:
            result = await analyze_page(i, image_path, vector_data, sheet_type)
            
            # Apply civil validation if needed
            if sheet_type == "civil":
                result = validate_civil_data(result)
                
        except Exception as e:
            result = {
                "page": i + 1,
                "detection_status": "error",
                "error": str(e)
            }
            failed_pages.append(i + 1)
        
        # Save individual page result
        page_output_file = os.path.join(output_dir, f"page_{i:04d}.json")
        with open(page_output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        page_results.append(result)
        
        # Update progress
        if progress_callback:
            progress = 30 + int((i + 1) / total_pages * 40)
            progress_callback(progress)
    
    # Stage 5: Consolidate results
    # Filter out error pages before consolidation
    valid_page_results = [r for r in page_results if "error" not in r]
    
    # Use appropriate schema based on sheet type
    final_schema = CIVIL_FINAL_SCHEMA if sheet_type == "civil" else FINAL_SCHEMA
    
    if not valid_page_results:
        # All pages failed
        final_result = json.loads(final_schema)
        final_result["status"] = "error"
        final_result["message"] = f"All {len(page_results)} pages failed to process."
        final_result["failed_pages"] = failed_pages
        final_result["pages"] = [r.get("page") for r in page_results]
    elif all(r.get("detection_status") == "no_elements_detected" for r in valid_page_results):
        final_result = json.loads(final_schema)
        final_result["status"] = "no_elements_detected"
        final_result["message"] = "No AEC elements were detected on any page."
        final_result["pages"] = [r.get("page") for r in valid_page_results]
        if failed_pages:
            final_result["failed_pages"] = failed_pages
            final_result["message"] += f" Pages {failed_pages} failed to process."
    else:
        try:
            final_result = await consolidate_results(valid_page_results, sheet_type)
            
            # Apply civil validation to consolidated result
            if sheet_type == "civil":
                final_result = validate_civil_consolidation(final_result)
            
            # Check if consolidation returned an error
            if "error" in final_result:
                final_result["status"] = "error"
                final_result["failed_pages"] = failed_pages
                if failed_pages:
                    final_result["message"] = f"Consolidation failed. Pages {failed_pages} had errors."
                else:
                    final_result["message"] = "Consolidation failed. Please try again."
            else:
                # Add failed pages info to successful result
                if failed_pages:
                    final_result["failed_pages"] = failed_pages
                    final_result["warning"] = f"Pages {failed_pages} failed to process and were excluded from consolidation."
        except Exception as e:
            final_result = json.loads(final_schema)
            final_result["status"] = "error"
            final_result["message"] = f"Consolidation failed: {str(e)}"
            final_result["failed_pages"] = failed_pages
    
    if progress_callback:
        progress_callback(80)
    
    # Stage 6: Save final result
    final_file = os.path.join(output_dir, "final_aec_model.json")
    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    if progress_callback:
        progress_callback(90)
    
    # Stage 7: Generate human-readable report
    if final_result.get("status") in ("no_images_detected", "no_elements_detected", "error"):
        markdown_report = build_no_data_report(final_result)
    else:
        try:
            markdown_report = await generate_markdown_report(final_result)
        except Exception as e:
            markdown_report = f"# Error Generating Report\n\nFailed to generate report: {str(e)}"
    
    # Save markdown report
    report_file = os.path.join(output_dir, "aec_human_readable_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    if progress_callback:
        progress_callback(100)
    
    return final_result
