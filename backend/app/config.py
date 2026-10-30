import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Resolve paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent

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

    # --- Groq LLM Configuration ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TEMPERATURE: float = 0.2
    GROQ_MAX_TOKENS: int = 1200

    # --- LLM Configuration (Updated for Colab / Legacy) ---
    LLM_ENDPOINT_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "llama3.1"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 1024
    USE_COLAB_LLM: bool = True
    COLAB_ENDPOINT_FILE: str = "colab_endpoint.txt"

    class Config:
        env_file = str(BASE_DIR / ".env")
        extra = "ignore"

settings = Settings()

# Automatic directory creation
for dir_path in [settings.UPLOAD_DIR, settings.CHUNK_DIR, settings.VECTOR_STORE_DIR, settings.MEMORY_DIR]:
    # Resolve relative paths relative to backend root
    resolved_path = BASE_DIR / dir_path
    os.makedirs(resolved_path, exist_ok=True)
