"""
Background Task Services
Services for managing asynchronous PDF processing tasks
"""
from typing import Dict
from pathlib import Path
import shutil
from aec_processor import process_pdf


async def process_pdf_background(session_id: str, sessions: Dict[str, dict]) -> None:
    """Background task to process PDF"""
    session = sessions[session_id]
    
    try:
        # Process the PDF
        result = await process_pdf(
            session["file_path"],
            session["output_dir"],
            progress_callback=lambda progress: update_progress(session_id, sessions, progress)
        )
        
        session["status"] = "completed"
        session["result"] = result
        session["progress"] = 100
        
        # Create zip file after processing completes
        output_dir = Path(session["output_dir"])
        zip_path = output_dir.parent / f"{session_id}_results.zip"
        create_results_zip(output_dir, zip_path)
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        session["progress"] = 0


def create_results_zip(output_dir: Path, zip_path: Path) -> None:
    """Create a zip file of the results directory"""
    # Remove existing zip if it exists
    if zip_path.exists():
        zip_path.unlink()
    
    # Create new zip
    shutil.make_archive(str(zip_path.with_suffix('')), 'zip', output_dir)


def update_progress(session_id: str, sessions: Dict[str, dict], progress: int) -> None:
    """Update processing progress"""
    if session_id in sessions:
        sessions[session_id]["progress"] = progress
