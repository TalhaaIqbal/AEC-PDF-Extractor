"""
Background Task Services
Services for managing asynchronous PDF processing tasks
"""
from typing import Dict
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
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        session["progress"] = 0


def update_progress(session_id: str, sessions: Dict[str, dict], progress: int) -> None:
    """Update processing progress"""
    if session_id in sessions:
        sessions[session_id]["progress"] = progress
