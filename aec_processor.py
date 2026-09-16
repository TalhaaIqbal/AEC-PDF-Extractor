"""
AEC Processor - Main Pipeline Orchestrator
Coordinates the PDF processing pipeline using modularized services
"""
import os
import json
from typing import Optional, Callable

from config.settings import PDF_DPI
from prompts import load_final_schema

FINAL_SCHEMA = load_final_schema()
from services.pdf_processor import classify_pdf_pages, extract_vector_data, render_page_images
from services.ai_analyzer import analyze_page, consolidate_results
from services.report_generator import build_no_data_report, generate_markdown_report


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
    page_images = render_page_images(pdf_path, page_image_dir, PDF_DPI)
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
    if all(r.get("detection_status") == "no_elements_detected" for r in page_results):
        final_result = json.loads(FINAL_SCHEMA)
        final_result["status"] = "no_elements_detected"
        final_result["message"] = "No AEC elements were detected on any page."
        final_result["pages"] = [r.get("page") for r in page_results]
    else:
        final_result = await consolidate_results(page_results)
    
    if progress_callback:
        progress_callback(80)
    
    # Stage 6: Save final result
    final_file = os.path.join(output_dir, "final_aec_model.json")
    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    if progress_callback:
        progress_callback(90)
    
    # Stage 7: Generate human-readable report
    if final_result.get("status") in ("no_images_detected", "no_elements_detected"):
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
