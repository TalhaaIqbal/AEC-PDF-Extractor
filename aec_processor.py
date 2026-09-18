"""
AEC Processor - Main Pipeline Orchestrator
Coordinates the PDF processing pipeline using modularized services
"""
import os
import json
import asyncio
from typing import Optional, Callable

from config.settings import PDF_DPI, LLM_MAX_IMAGE_DIMENSION, FINAL_SCHEMA
from services import (
    classify_pdf_pages_async, 
    extract_vector_data_async, 
    render_page_images_async,
    analyze_page, 
    consolidate_results,
    build_no_data_report, 
    generate_markdown_report
)


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
    page_info = await classify_pdf_pages_async(pdf_path)
    has_pages = len(page_info) > 0
    
    if not has_pages:
        result = {
            "status": "no_images_detected",
            "message": "This PDF has zero pages."
        }
        return result
    
    if progress_callback:
        progress_callback(10)
    
    # Stage 2: Extract vector data for vector pages in parallel
    vector_data_by_page = {}
    vector_pages = [page for page in page_info if page["is_vector"]]
    
    if vector_pages:
        # Extract vector data for all vector pages in parallel
        vector_tasks = [
            extract_vector_data_async(pdf_path, page["page"])
            for page in vector_pages
        ]
        vector_results = await asyncio.gather(*vector_tasks)
        
        # Map results back to page numbers
        for page, result in zip(vector_pages, vector_results):
            vector_data_by_page[page["page"]] = result
    
    if progress_callback:
        progress_callback(20)
    
    # Stage 3: Render page images
    page_image_dir = os.path.join(output_dir, "pdf_pages")
    page_images = await render_page_images_async(pdf_path, page_image_dir, PDF_DPI, LLM_MAX_IMAGE_DIMENSION)
    has_page_images = len(page_images) > 0
    
    if not has_page_images:
        result = {
            "status": "no_images_detected",
            "message": "No page images could be rendered."
        }
        return result
    
    if progress_callback:
        progress_callback(30)
    
    # Stage 4: Process each page in parallel with concurrency limit
    page_results = []
    failed_pages = []
    total_pages = len(page_images)
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent API calls
    
    async def process_single_page(i: int, image_path: str) -> dict:
        """Process a single page with retry logic for rate limits"""
        vector_data = vector_data_by_page.get(i)
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                async with semaphore:
                    result = await analyze_page(i, image_path, vector_data)
                    return result
            except Exception as e:
                error_str = str(e).lower()
                # Check if it's a rate limit error
                is_rate_limit = any(term in error_str for term in ['rate limit', '429', 'too many requests', 'quota'])
                
                if attempt < max_retries - 1 and is_rate_limit:
                    # Exponential backoff for rate limits
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Final attempt or non-rate-limit error
                    result = {
                        "page": i + 1,
                        "detection_status": "error",
                        "error": str(e)
                    }
                    return result
    
    # Create tasks for all pages
    tasks = [process_single_page(i, image_path) for i, image_path in enumerate(page_images)]
    
    # Process pages in parallel and collect results
    page_results = await asyncio.gather(*tasks)
    
    # Save individual page results and track failures
    for i, result in enumerate(page_results):
        if result.get("detection_status") == "error":
            failed_pages.append(i + 1)
        
        # Save individual page result
        page_output_file = os.path.join(output_dir, f"page_{i:04d}.json")
        with open(page_output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    # Update progress
    if progress_callback:
        progress_callback(70)
    
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
