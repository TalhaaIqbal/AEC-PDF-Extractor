"""
AEC Processor - Main Pipeline Orchestrator
Coordinates the PDF processing pipeline using modularized services
"""
import os
import json
import asyncio
from typing import Optional, Callable

from config.settings import PDF_DPI, LLM_MAX_IMAGE_DIMENSION, FINAL_SCHEMA, REGION_CROP_DPI, REGION_ENHANCEMENT_METHOD, MIN_REGION_SIZE, TEMP_DIR, TEXT_ENHANCEMENT_ENABLED, CONTRAST_ENHANCEMENT
from services import (
    classify_pdf_pages_async, 
    extract_vector_data_async, 
    render_page_images_async,
    analyze_page, 
    consolidate_results,
    build_no_data_report, 
    generate_markdown_report,
    detect_regions,
    analyze_crop,
    process_regions_for_page_async
)


def merge_crop_results(crop_results: list) -> dict:
    """
    Merge results from multiple crop analyses into page-level results
    
    Args:
        crop_results: List of crop analysis results
    
    Returns:
        Merged page-level result with all elements from crops
    """
    merged = {
        "stations": [],
        "match_lines": [],
        "curb_gutter": [],
        "ramps": [],
        "right_of_way": [],
        "work_limits": [],
        "hatched_areas": [],
        "levels": [],
        "grids": [],
        "rooms": [],
        "walls": [],
        "doors": [],
        "windows": [],
        "columns": [],
        "stairs": [],
        "dimensions": [],
        "elevations": [],
        "annotations": [],
        "materials": [],
        "notes": [],
        "relationships": []
    }
    
    # Element types to merge
    element_types = [
        "stations", "match_lines", "curb_gutter", "ramps", "right_of_way", 
        "work_limits", "hatched_areas", "levels", "grids", "rooms", 
        "walls", "doors", "windows", "columns", "stairs", "dimensions", 
        "elevations", "annotations", "materials", "notes", "relationships"
    ]
    
    # Merge elements from all successful crop results
    for crop_result in crop_results:
        if crop_result.get("detection_status") == "error":
            continue
            
        region_id = crop_result.get("region_id", "unknown")
        
        for element_type in element_types:
            if element_type in crop_result and isinstance(crop_result[element_type], list):
                # Add region_id to each element to track source
                for element in crop_result[element_type]:
                    if isinstance(element, dict):
                        element["source_region"] = region_id
                merged[element_type].extend(crop_result[element_type])
    
    return merged


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
    
    print(f"Starting PDF processing with {len(page_info)} pages")
    has_pages = len(page_info) > 0
    
    if not has_pages:
        result = {
            "status": "no_images_detected",
            "message": "This PDF has zero pages."
        }
        return result
    
    if progress_callback:
        progress_callback(10)
    
    vector_count = len([p for p in page_info if p.get("is_vector")])
    scanned_count = len(page_info) - vector_count
    print(f"Page classification: {vector_count} vector pages, {scanned_count} scanned pages")
    
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
    
    print(f"Vector data extraction completed for {len(vector_data_by_page)} pages")
    
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
    
    print(f"Page rendering completed: {len(page_images)} pages rendered")
    
    # Stage 4: Process each page with type-specific workflow
    page_results = []
    failed_pages = []
    total_pages = len(page_images)
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent API calls
    crop_semaphore = asyncio.Semaphore(3)  # Limit concurrent crop analysis
    
    # Stage 4: Process each page with type-specific workflow
    page_results = []
    failed_pages = []
    total_pages = len(page_images)
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent API calls
    crop_semaphore = asyncio.Semaphore(3)  # Limit concurrent crop analysis
    
    async def process_single_page(i: int, image_path: str, page_info: dict) -> dict:
        """Process a single page with type-specific workflow"""
        vector_data = vector_data_by_page.get(i)
        is_vector = page_info.get("is_vector", False)
        max_retries = 3
        base_delay = 2  # seconds
        
        try:
            if is_vector:
                # Vector PDF: Use existing single-pass workflow
                print(f"Page {i + 1}: Vector page - using single-pass analysis")
                async with semaphore:
                    result = await analyze_page(i, image_path, vector_data)
                    return result
            else:
                # Scanned PDF: Use two-stage workflow
                print(f"Page {i + 1}: Scanned page - using two-stage workflow")
                
                # Stage 4a: Region detection
                region_detection = await detect_regions(i, image_path, vector_data)
                
                # Check if regions need close inspection
                if region_detection.get("requires_close_inspection", False) and region_detection.get("regions"):
                    print(f"Page {i + 1}: Found {len(region_detection['regions'])} regions requiring close inspection")
                    
                    # Stage 4b: Process regions (crop + enhance)
                    regions_output_dir = os.path.join(TEMP_DIR, f"page_{i:04d}_regions")
                    processed_regions = await process_regions_for_page_async(
                        image_path,
                        region_detection["regions"],
                        regions_output_dir,
                        REGION_CROP_DPI,
                        REGION_ENHANCEMENT_METHOD,
                        MIN_REGION_SIZE,
                        TEXT_ENHANCEMENT_ENABLED,
                        CONTRAST_ENHANCEMENT
                    )
                    
                    # Stage 4c: Analyze each processed crop in parallel
                    crop_results = []
                    sheet_type = region_detection.get("sheet_type", "architectural")
                    
                    async def process_single_crop(region_data: dict) -> dict:
                        """Process a single crop with retry logic"""
                        enhanced_path = region_data.get("enhanced_path")
                        if not enhanced_path or region_data.get("processing_status") != "success":
                            return {
                                "region_id": region_data.get("region_id"),
                                "detection_status": "error",
                                "error": "Crop processing failed"
                            }
                        
                        for attempt in range(max_retries):
                            try:
                                async with crop_semaphore:
                                    result = await analyze_crop(enhanced_path, region_data, sheet_type)
                                    return result
                            except Exception as e:
                                error_str = str(e).lower()
                                is_rate_limit = any(term in error_str for term in ['rate limit', '429', 'too many requests', 'quota'])
                                
                                if attempt < max_retries - 1 and is_rate_limit:
                                    delay = base_delay * (2 ** attempt)
                                    await asyncio.sleep(delay)
                                    continue
                                else:
                                    return {
                                        "region_id": region_data.get("region_id"),
                                        "detection_status": "error",
                                        "error": str(e)
                                    }
                    
                    # Process all crops in parallel
                    crop_tasks = [process_single_crop(region) for region in processed_regions]
                    crop_results = await asyncio.gather(*crop_tasks)
                    
                    # Combine crop results into page-level result
                    combined_result = {
                        "page": i + 1,
                        "detection_status": "ok",
                        "sheet_type": sheet_type,
                        "processing_method": "crop_based",
                        "regions_processed": len(processed_regions),
                        "regions_analyzed": len([r for r in crop_results if r.get("detection_status") != "error"]),
                        "crop_results": crop_results,
                        "region_detection": region_detection
                    }
                    
                    # Merge crop results into standard schema format
                    # This consolidates all crop data into page-level results
                    merged_elements = merge_crop_results(crop_results)
                    combined_result.update(merged_elements)
                    
                    return combined_result
                else:
                    # No regions need close inspection - use enhanced single-pass
                    print(f"Page {i + 1}: No regions requiring close inspection - using enhanced single-pass analysis")
                    async with semaphore:
                        result = await analyze_page(i, image_path, vector_data)
                        result["processing_method"] = "enhanced_single_pass"
                        result["region_detection"] = region_detection
                        return result
                        
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a rate limit error
            is_rate_limit = any(term in error_str for term in ['rate limit', '429', 'too many requests', 'quota'])
            
            if is_rate_limit:
                # For rate limits, we could retry at a higher level, but for now return error
                print(f"Page {i + 1}: Rate limit encountered - {e}")
            
            result = {
                "page": i + 1,
                "detection_status": "error",
                "error": str(e)
            }
            return result
    
    # Create tasks for all pages with page info
    tasks = [process_single_page(i, image_path, current_page_info) for i, (image_path, current_page_info) in enumerate(zip(page_images, page_info))]
    
    print(f"Starting parallel processing of {len(tasks)} pages")
    
    # Process pages in parallel and collect results
    page_results = await asyncio.gather(*tasks)
    
    # Update progress
    if progress_callback:
        progress_callback(70)
    
    # Save individual page results and track failures
    for i, result in enumerate(page_results):
        if result.get("detection_status") == "error":
            failed_pages.append(i + 1)
        
        # Save individual page result
        page_output_file = os.path.join(output_dir, f"page_{i:04d}.json")
        with open(page_output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Page processing completed: {len(page_results)} pages processed, {len(failed_pages)} failed")
    
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
