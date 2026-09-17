"""
File Helper Utilities
Utility functions for file operations and cleanup
"""
import shutil
from pathlib import Path


def cleanup_session(session_id: str, upload_dir: Path, output_dir: Path) -> None:
    """Clean up session files"""
    try:
        session_upload_dir = upload_dir / session_id
        session_output_dir = output_dir / session_id
        
        if session_upload_dir.exists():
            shutil.rmtree(session_upload_dir)
        
        if session_output_dir.exists():
            shutil.rmtree(session_output_dir)
        
        # Also clean up zip file if it exists
        zip_path = output_dir.parent / f"{session_id}_results.zip"
        if zip_path.exists():
            zip_path.unlink()
    
    except Exception as e:
        print(f"Error cleaning up session {session_id}: {e}")
