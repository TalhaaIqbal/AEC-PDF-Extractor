"""
PDF Processing Service
Handles PDF page classification, vector data extraction, and image rendering
"""
import os
import shutil
from typing import List, Dict, Any
import pymupdf  # PyMuPDF


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

    paths = []
    for d in drawings:
        rect = d.get("rect")
        paths.append({
            "type": d.get("type"),
            "rect": [round(v, 1) for v in rect] if rect else None,
            "stroke_width": d.get("width"),
            "item_count": len(d.get("items", []))
        })

    return {"texts": texts, "paths": paths}


def render_page_images(pdf_path: str, output_dir: str, dpi: int = 250) -> List[str]:
    """
    Render PDF pages to images
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save rendered images
        dpi: DPI for rendering
    
    Returns:
        List of paths to rendered images
    """
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    page_paths = []

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        path = os.path.join(output_dir, f"page_{i:04d}.jpg")
        pix.save(path)
        page_paths.append(path)

    doc.close()
    return page_paths
