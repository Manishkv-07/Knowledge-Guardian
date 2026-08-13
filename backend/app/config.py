import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8087

    # Directory paths (relative to backend folder or absolute)
    UPLOAD_DIR: str = "data/uploads"
    CHUNK_DIR: str = "data/chunks"
    VECTOR_STORE_DIR: str = "data/vector_store"
    MEMORY_DIR: str = "data/memory"

    # Embedding and splitting configurations
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # FAISS settings
    FAISS_INDEX_NAME: str = "faiss.index"
    INDEX_FILE: str = "knowledge_index.faiss"
    METADATA_FILE: str = "metadata.json"

    # Modal endpoint configurations
    MODAL_ENDPOINT_URL: str = ""
    MODAL_API_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Resolve paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Automatic directory creation
for dir_path in [settings.UPLOAD_DIR, settings.CHUNK_DIR, settings.VECTOR_STORE_DIR, settings.MEMORY_DIR]:
    # Resolve relative paths relative to backend root
    resolved_path = BASE_DIR / dir_path
    os.makedirs(resolved_path, exist_ok=True)
