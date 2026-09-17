"""
AEC Processor - Main Pipeline Orchestrator
Coordinates the PDF processing pipeline using modularized services
"""
import os
import json
from typing import Optional, Callable

from config.settings import PDF_DPI, LLM_MAX_IMAGE_DIMENSION, FINAL_SCHEMA
from services.pdf_processor import classify_pdf_pages, extract_vector_data, render_page_images
from services.ai_analyzer import analyze_page, consolidate_results
from services.report_generator import build_no_data_report, generate_markdown_report


async def process_pdf(pdf_path: str, output_dir: str, progress_callback: Optional[Callable[[int], None]] = None):
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
    
    for i, image_path in enumerate(page_images):
        vector_data = vector_data_by_page.get(i)
        
        try:
            result = await analyze_page(i, image_path, vector_data)
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
    valid_page_results = [r for r in page_results if r.get("detection_status") != "error"]
    
    if not valid_page_results:
        # All pages failed
        final_result = {
            "status": "all_pages_failed",
            "message": f"All {len(page_results)} pages failed to process.",
            "error_pages": failed_pages,
            "total_pages": len(page_results)
        }
    elif all(r.get("detection_status") == "no_elements_detected" for r in valid_page_results):
        final_result = json.loads(FINAL_SCHEMA)
        final_result["status"] = "no_elements_detected"
        final_result["message"] = "No AEC elements were detected on any page."
        final_result["pages"] = [r.get("page") for r in valid_page_results]
        if failed_pages:
            final_result["error_pages"] = failed_pages
            final_result["message"] += f" Some pages ({len(failed_pages)}) failed to process."
    else:
        try:
            final_result = await consolidate_results(valid_page_results)
            # Add error page information to the result
            if failed_pages:
                final_result["error_pages"] = failed_pages
                final_result["error_page_count"] = len(failed_pages)
        except Exception as e:
            # Consolidation failed
            final_result = {
                "status": "consolidation_failed",
                "message": f"Failed to consolidate page results: {str(e)}",
                "error": str(e),
                "error_pages": failed_pages,
                "total_pages": len(page_results),
                "successful_pages": len(valid_page_results)
            }
    
    if progress_callback:
        progress_callback(80)
    
    # Stage 6: Save final result
    final_file = os.path.join(output_dir, "final_aec_model.json")
    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    if progress_callback:
        progress_callback(90)
    
    # Stage 7: Generate human-readable report
    error_statuses = ("no_images_detected", "no_elements_detected", "all_pages_failed", "consolidation_failed")
    if final_result.get("status") in error_statuses:
        markdown_report = build_no_data_report(final_result)
    else:
        markdown_report = await generate_markdown_report(final_result)
    
    # Save markdown report
    report_file = os.path.join(output_dir, "aec_human_readable_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    if progress_callback:
        progress_callback(100)
    
    return final_result
