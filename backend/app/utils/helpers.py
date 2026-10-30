import os
import re
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

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md', 'html', 'htm'}

def is_allowed_file(filename: str) -> bool:
    """Check if the uploaded file is a PDF, TXT, MD, or HTML document."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_file_size(size_in_bytes: int) -> str:
    """Format file size into human-readable strings."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} TB"

def clean_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid filesystem characters."""
    base = Path(filename).name
    # Replace any potentially dangerous path/shell characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '_', base)
    return sanitized if sanitized else "uploaded_document"
