import os
from pathlib import Path
import logging

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("knowledge_guardian")

def is_allowed_file(filename: str) -> bool:
    """Check if the uploaded file is a PDF, TXT, or MD."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'txt', 'md'}

def format_file_size(size_in_bytes: int) -> str:
    """Format file size into human-readable strings."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} TB"

def clean_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal."""
    return Path(filename).name
