"""
Image Processing Service
Handles cropping, enhancement, and processing of image regions
"""
import os
import asyncio
from typing import Dict, Any, List, Tuple
from pathlib import Path
from PIL import Image
import io

__all__ = [
    'crop_region',
    'crop_region_async',
    'enhance_image',
    'enhance_image_async',
    'process_regions_for_page',
    'process_regions_for_page_async'
]


def crop_region(image_path: str, bbox: Dict[str, float], output_path: str) -> str:
    """
    Crop a region from an image based on normalized bounding box coordinates
    
    Args:
        image_path: Path to source image
        bbox: Normalized bounding box {"x": 0-1, "y": 0-1, "width": 0-1, "height": 0-1}
        output_path: Path to save cropped image
    
    Returns:
        Path to cropped image
    """
    img = Image.open(image_path)
    img_width, img_height = img.size
    
    # Convert normalized coordinates to pixel coordinates
    x = int(bbox["x"] * img_width)
    y = int(bbox["y"] * img_height)
    width = int(bbox["width"] * img_width)
    height = int(bbox["height"] * img_height)
    
    # Ensure coordinates are within image bounds
    x = max(0, min(x, img_width - 1))
    y = max(0, min(y, img_height - 1))
    width = max(1, min(width, img_width - x))
    height = max(1, min(height, img_height - y))
    
    # Crop the image
    cropped = img.crop((x, y, x + width, y + height))
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save cropped image
    cropped.save(output_path, "PNG")
    img.close()
    
    return output_path


async def crop_region_async(image_path: str, bbox: Dict[str, float], output_path: str) -> str:
    """
    Async wrapper for crop_region
    """
    return await asyncio.to_thread(crop_region, image_path, bbox, output_path)


def enhance_image(image_path: str, target_dpi: int, output_path: str, method: str = "LANCZOS", text_enhancement: bool = False, contrast_enhancement: bool = False) -> str:
    """
    Enhance and upscale an image to target DPI with optional text and contrast enhancement
    
    Args:
        image_path: Path to source image
        target_dpi: Target DPI for enhancement
        output_path: Path to save enhanced image
        method: Resampling method (LANCZOS, BICUBIC, BILINEAR)
        text_enhancement: Enable text-specific enhancement for better OCR
        contrast_enhancement: Enable contrast enhancement for better text recognition
    
    Returns:
        Path to enhanced image
    """
    img = Image.open(image_path)
    original_width, original_height = img.size
    
    # Calculate scaling factor based on DPI assumption (assuming original at 72 DPI)
    scaling_factor = target_dpi / 72.0
    
    # Calculate new dimensions
    new_width = int(original_width * scaling_factor)
    new_height = int(original_height * scaling_factor)
    
    # Choose resampling method
    resampling_method = Image.Resampling.LANCZOS
    if method.upper() == "BICUBIC":
        resampling_method = Image.Resampling.BICUBIC
    elif method.upper() == "BILINEAR":
        resampling_method = Image.Resampling.BILINEAR
    
    # Resize image
    enhanced = img.resize((new_width, new_height), resampling_method)
    
    # Apply text-specific enhancement if enabled
    if text_enhancement:
        # Convert to grayscale for better text processing
        if enhanced.mode != "L":
            enhanced = enhanced.convert("L")
        
        # Apply slight sharpening for text clarity
        from PIL import ImageFilter
        enhanced = enhanced.filter(ImageFilter.SHARPEN)
        
        # Apply mild contrast enhancement
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.2)  # 20% contrast increase
    
    # Apply contrast enhancement if enabled (for color images)
    elif contrast_enhancement and enhanced.mode != "L":
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.3)  # 30% contrast increase
        
        # Also enhance brightness slightly
        brightness_enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = brightness_enhancer.enhance(1.1)  # 10% brightness increase
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save enhanced image
    enhanced.save(output_path, "PNG")
    img.close()
    
    return output_path


async def enhance_image_async(image_path: str, target_dpi: int, output_path: str, method: str = "LANCZOS", text_enhancement: bool = False, contrast_enhancement: bool = False) -> str:
    """
    Async wrapper for enhance_image
    """
    return await asyncio.to_thread(enhance_image, image_path, target_dpi, output_path, method, text_enhancement, contrast_enhancement)


def process_regions_for_page(page_image_path: str, regions: List[Dict[str, Any]], output_dir: str, target_dpi: int = 400, enhancement_method: str = "LANCZOS", min_region_size: int = 100, text_enhancement: bool = False, contrast_enhancement: bool = False) -> List[Dict[str, Any]]:
    """
    Process all regions for a page: crop and enhance each region
    
    Args:
        page_image_path: Path to full page image
        regions: List of region dictionaries with bbox and metadata
        output_dir: Directory to save processed regions
        target_dpi: Target DPI for enhancement
        enhancement_method: Resampling method for enhancement
        min_region_size: Minimum pixel size for viable crop
        text_enhancement: Enable text-specific enhancement for better OCR
        contrast_enhancement: Enable contrast enhancement for better text recognition
    
    Returns:
        List of processed region info with paths
    """
    img = Image.open(page_image_path)
    img_width, img_height = img.size
    img.close()
    
    processed_regions = []
    
    for i, region in enumerate(regions):
        bbox = region.get("bbox", {})
        region_id = region.get("region_id", f"region_{i}")
        region_type = region.get("region_type", "unknown")
        
        # Calculate actual pixel size
        pixel_width = int(bbox.get("width", 0) * img_width)
        pixel_height = int(bbox.get("height", 0) * img_height)
        
        # Skip regions that are too small
        if pixel_width < min_region_size or pixel_height < min_region_size:
            print(f"Skipping region {region_id}: too small ({pixel_width}x{pixel_height})")
            continue
        
        # Create output paths
        crop_path = os.path.join(output_dir, f"{region_id}_crop.png")
        enhanced_path = os.path.join(output_dir, f"{region_id}_enhanced.png")
        
        try:
            # Crop the region
            crop_region(page_image_path, bbox, crop_path)
            
            # Determine enhancement settings based on region type
            region_text_enhancement = text_enhancement
            region_contrast_enhancement = contrast_enhancement
            
            # Enable text enhancement for regions likely to contain text
            if region_type in ["schedule", "annotation", "title_block", "legend"]:
                region_text_enhancement = True
            
            # Enhance the cropped region
            enhance_image(crop_path, target_dpi, enhanced_path, enhancement_method, region_text_enhancement, region_contrast_enhancement)
            
            processed_regions.append({
                **region,
                "crop_path": crop_path,
                "enhanced_path": enhanced_path,
                "processing_status": "success",
                "enhancement_settings": {
                    "text_enhancement": region_text_enhancement,
                    "contrast_enhancement": region_contrast_enhancement
                }
            })
            
        except Exception as e:
            print(f"Error processing region {region_id}: {e}")
            processed_regions.append({
                **region,
                "processing_status": "error",
                "error": str(e)
            })
    
    return processed_regions


async def process_regions_for_page_async(page_image_path: str, regions: List[Dict[str, Any]], output_dir: str, target_dpi: int = 400, enhancement_method: str = "LANCZOS", min_region_size: int = 100, text_enhancement: bool = False, contrast_enhancement: bool = False) -> List[Dict[str, Any]]:
    """
    Async wrapper for process_regions_for_page
    """
    return await asyncio.to_thread(process_regions_for_page, page_image_path, regions, output_dir, target_dpi, enhancement_method, min_region_size, text_enhancement, contrast_enhancement)