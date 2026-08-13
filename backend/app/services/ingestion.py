import os
import json
import uuid
import datetime
from typing import List, Dict, Any
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pathlib import Path
from app.config import settings
from app.utils.helpers import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class IngestionService:
    def __init__(self):
        # Initialize text splitter with configured chunk size and overlap
        logger.info(f"Initializing text splitter: chunk_size={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP}")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len
        )
    
    def _save_chunks(self, document_id: str, chunks: List[Dict[str, Any]]) -> str:
        """Saves generated chunks to data/chunks/{document_id}.json"""
        chunks_dir = BASE_DIR / settings.CHUNK_DIR
        os.makedirs(chunks_dir, exist_ok=True)
        
        file_path = chunks_dir / f"{document_id}.json"
        logger.info(f"Saving {len(chunks)} chunks to: {file_path}")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
            
        return str(file_path)

    def process_pdf(self, file_path: str, filename: str, document_id: str = None) -> dict:
        """Extract text from PDF using PyMuPDF, split into chunks, save to disk
        Returns: {
            "document_id": str,
            "chunks": List[dict],
            "total_chunks": int
        }
        """
        logger.info(f"Processing PDF file: {filename} at {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            doc = fitz.open(file_path)
            raw_text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                if page_text:
                    raw_text += page_text + "\n"
            doc.close()
            
            if not raw_text.strip():
                raise ValueError(f"Could not extract any text from PDF: {filename} (empty or scanned image)")
                
        except Exception as e:
            logger.error(f"Error reading PDF {filename}: {e}")
            raise ValueError(f"Failed to parse PDF document: {str(e)}")

        return self._create_and_save_chunks(raw_text, filename, document_id)

    def process_text(self, file_path: str, filename: str, document_id: str = None) -> dict:
        """Extract text from TXT/MD files, split into chunks
        Returns: Same structure as process_pdf
        """
        logger.info(f"Processing text file: {filename} at {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
                
            if not raw_text.strip():
                raise ValueError(f"File is empty: {filename}")
                
        except Exception as e:
            logger.error(f"Error reading text file {filename}: {e}")
            raise ValueError(f"Failed to read text file: {str(e)}")

        return self._create_and_save_chunks(raw_text, filename, document_id)

    def _create_and_save_chunks(self, text: str, filename: str, document_id: str = None) -> dict:
        """Helper to split text, build metadata structures, and write chunks to disk."""
        # 1. Generate unique document_id if not supplied
        if not document_id:
            document_id = str(uuid.uuid4())
        
        # 2. Split text
        text_chunks = self.text_splitter.split_text(text)
        total_chunks = len(text_chunks)
        
        if total_chunks == 0:
            raise ValueError("Document yielded no text chunks after splitting.")
            
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        chunks_list = []
        
        # 3. Create formatted chunk records
        for i, chunk_text in enumerate(text_chunks):
            chunk_id = f"{document_id}_{i}"
            chunks_list.append({
                "id": chunk_id,
                "document_id": document_id,
                "text": chunk_text,
                "metadata": {
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "timestamp": timestamp,
                    "char_count": len(chunk_text)
                }
            })
            
        # 4. Save to disk
        self._save_chunks(document_id, chunks_list)
        
        return {
            "document_id": document_id,
            "chunks": chunks_list,
            "total_chunks": total_chunks
        }

    def get_chunks_by_document(self, document_id: str) -> list:
        """Retrieve all chunks for a specific document from disk"""
        chunks_file = BASE_DIR / settings.CHUNK_DIR / f"{document_id}.json"
        logger.info(f"Retrieving chunks from: {chunks_file}")
        
        if not os.path.exists(chunks_file):
            logger.warning(f"No chunks file found for document ID: {document_id}")
            return []
            
        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading chunks from {chunks_file}: {e}")
            return []

ingestion_service = IngestionService()
