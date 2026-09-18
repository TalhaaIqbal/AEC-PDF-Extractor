"""
PDF Processing Service
Handles PDF page classification, vector data extraction, and image rendering
"""
import os
import shutil
import asyncio
from typing import List, Dict, Any
import pymupdf  # PyMuPDF

__all__ = [
    'classify_pdf_pages',
    'classify_pdf_pages_async',
    'extract_vector_data',
    'extract_vector_data_async',
    'render_page_images',
    'render_page_images_async'
]


def classify_pdf_pages(pdf_path: str, min_text_chars: int = 20, min_vector_paths: int = 5) -> List[Dict[str, Any]]:
    """
    Classify each page as vector (native) or scanned/raster
    
    Args:
        pdf_path: Path to the PDF file
        min_text_chars: Minimum text characters to consider a page as vector
        min_vector_paths: Minimum vector paths to consider a page as vector
    
    Returns:
        List of page information dictionaries
    """
    doc = pymupdf.open(pdf_path)
    page_info = []

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        drawings = page.get_drawings()

        is_vector = (
            len(text) >= min_text_chars
            or len(drawings) >= min_vector_paths
        )

        page_info.append({
            "page": i,
            "is_vector": is_vector,
            "text_char_count": len(text),
            "vector_path_count": len(drawings)
        })

    doc.close()
    return page_info


async def classify_pdf_pages_async(pdf_path: str, min_text_chars: int = 20, min_vector_paths: int = 5) -> List[Dict[str, Any]]:
    """
    Async wrapper for classify_pdf_pages - runs blocking PyMuPDF operations in thread pool
    
    Args:
        pdf_path: Path to the PDF file
        min_text_chars: Minimum text characters to consider a page as vector
        min_vector_paths: Minimum vector paths to consider a page as vector
    
    Returns:
        List of page information dictionaries
    """
    return await asyncio.to_thread(classify_pdf_pages, pdf_path, min_text_chars, min_vector_paths)


def extract_vector_data(pdf_path: str, page_index: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract native vector data (text + geometry) from a page
    
    Args:
        pdf_path: Path to the PDF file
        page_index: Index of the page to extract data from
    
    Returns:
        Dictionary containing texts and paths
    """
    doc = pymupdf.open(pdf_path)
    page = doc[page_index]

    text_dict = page.get_text("dict")
    drawings = page.get_drawings()

    doc.close()

    texts = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["text"].strip():
                    texts.append({
                        "text": span["text"],
                        "bbox": [round(v, 1) for v in span["bbox"]],
                        "font_size": round(span["size"], 1)
                    })

    # Instead of sending thousands of individual paths (noise), provide a summary
    # Focus budget on text spans which are more useful for extraction
    path_summary = {
        "total_paths": len(drawings),
        "path_types": {},
        "has_geometry": len(drawings) > 0
    }
    
    # Count path types for summary
    for d in drawings:
        path_type = d.get("type", "unknown")
        path_summary["path_types"][path_type] = path_summary["path_types"].get(path_type, 0) + 1

    return {"texts": texts, "paths": path_summary}


async def extract_vector_data_async(pdf_path: str, page_index: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Async wrapper for extract_vector_data - runs blocking PyMuPDF operations in thread pool
    
    Args:
        pdf_path: Path to the PDF file
        page_index: Index of the page to extract data from
    
    Returns:
        Dictionary containing texts and paths
    """
    return await asyncio.to_thread(extract_vector_data, pdf_path, page_index)


def render_page_images(pdf_path: str, output_dir: str, dpi: int = 250, max_dimension: int = 2000) -> List[str]:
    """
    Render PDF pages to images at optimal resolution for LLM processing
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save rendered images
        dpi: DPI for rendering (default 250, but images will be resized to max_dimension)
        max_dimension: Maximum dimension (width or height) for output images
    
    Returns:
        List of paths to rendered images
    """
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    page_paths = []

    for i, page in enumerate(doc):
        # Calculate optimal DPI to directly render at target size
        rect = page.rect
        max_page_dim = max(rect.width, rect.height)
        optimal_dpi = min(dpi, int(max_dimension / max_page_dim * 72))

        # Render at optimal DPI to avoid wasteful high-res rendering
        # Use PNG format for better line drawing quality (no JPEG compression artifacts)
        pix = page.get_pixmap(dpi=optimal_dpi, alpha=False)
        path = os.path.join(output_dir, f"page_{i:04d}.png")
        pix.save(path)
        page_paths.append(path)

    doc.close()
    return page_paths


async def render_page_images_async(pdf_path: str, output_dir: str, dpi: int = 250, max_dimension: int = 2000) -> List[str]:
    """
    Async wrapper for render_page_images - runs blocking PyMuPDF operations in thread pool
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save rendered images
        dpi: DPI for rendering (default 250, but images will be resized to max_dimension)
        max_dimension: Maximum dimension (width or height) for output images
    
    Returns:
        List of paths to rendered images
    """
    return await asyncio.to_thread(render_page_images, pdf_path, output_dir, dpi, max_dimension)
