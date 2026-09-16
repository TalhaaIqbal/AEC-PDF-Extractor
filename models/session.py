"""
Session Data Model
Pydantic model for session data structure and validation
"""
from typing import Optional, Any
from pydantic import BaseModel


class Session(BaseModel):
    """Session data model for tracking PDF processing state"""
    status: str = "uploaded"
    filename: str
    file_path: str
    output_dir: str
    progress: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
