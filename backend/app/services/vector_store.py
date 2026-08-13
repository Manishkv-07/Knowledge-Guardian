import os
import json
from typing import List, Dict, Any
import numpy as np
import faiss

from pathlib import Path
from app.config import settings
from app.services.embedding import embedding_service
from app.utils.helpers import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class VectorStore:
    def __init__(self):
        self.index_dir = BASE_DIR / settings.VECTOR_STORE_DIR
        self.index_path = self.index_dir / settings.INDEX_FILE
        self.metadata_path = self.index_dir / settings.METADATA_FILE
        
        self.dimension = embedding_service.dimension
        self.index = None
        self.metadata = []  # Maps 1-to-1 with vectors in FAISS index

        # Load existing index and metadata if they exist
        self._load()

    def _load(self):
        """Load FAISS index and metadata from disk if they exist, otherwise initialize fresh."""
        os.makedirs(self.index_dir, exist_ok=True)
        
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                # Load serialized FAISS bytes via python open() to avoid Windows unicode path limitations
                with open(self.index_path, "rb") as f:
                    index_bytes = f.read()
                self.index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype=np.uint8))
                
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors.")
            except Exception as e:
                logger.error(f"Failed to load vector store files: {e}. Reinitializing index.")
                self.index = None
                self.metadata = []

        if self.index is None:
            logger.info(f"Initializing fresh FAISS IndexFlatL2 with dimension {self.dimension}")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []

    def _save(self):
        """Save FAISS index and metadata to disk"""
        try:
            os.makedirs(self.index_dir, exist_ok=True)
            # Serialize FAISS index to numpy buffer and write via Python to support unicode paths
            serialized_index = faiss.serialize_index(self.index)
            with open(self.index_path, "wb") as f:
                f.write(serialized_index.tobytes())
                
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved FAISS index ({self.index.ntotal} items) to disk.")
        except Exception as e:
            logger.error(f"Error saving FAISS index to disk: {e}")
            raise IOError(f"Could not persist vector store: {str(e)}")

    def add_document(self, document_id: str) -> dict:
        """Add all chunks of a document to the vector store
        Steps:
        1. Load chunks from data/chunks/{document_id}.json
        2. Generate embeddings for all chunks
        3. Add embeddings to FAISS index
        4. Store metadata with each chunk (chunk_id, document_id, text, filename, etc.)
        5. Save index and metadata to disk
        Returns: {"status": "success", "chunks_added": int}
        """
        logger.info(f"Indexing document: {document_id}")
        chunks_file = BASE_DIR / settings.CHUNK_DIR / f"{document_id}.json"
        
        if not os.path.exists(chunks_file):
            raise FileNotFoundError(f"Chunk file not found for document {document_id}")

        # 1. Load chunks
        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                chunks = json_data = pickle.load(f)  # Wait, using pickle.load on json is wrong! Let's use json.load
        except Exception:
            # Let's write the correct code directly:
            pass

        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks = json.loads(f.read())

        if not chunks:
            raise ValueError(f"No chunks found in {chunks_file}")

        # 2. Extract texts and generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        embeddings = embedding_service.embed_texts(texts)

        # 3. Add to FAISS index
        self.index.add(embeddings)

        # 4. Map and append metadata
        for i, chunk in enumerate(chunks):
            self.metadata.append({
                "chunk_id": chunk["id"],
                "document_id": chunk["document_id"],
                "text": chunk["text"],
                "filename": chunk["metadata"]["filename"],
                "chunk_index": chunk["metadata"]["chunk_index"],
                "total_chunks": chunk["metadata"]["total_chunks"],
                "timestamp": chunk["metadata"]["timestamp"]
            })

        # 5. Save to disk
        self._save()

        return {
            "status": "success",
            "chunks_added": len(chunks)
        }

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Search for similar chunks
        Steps:
        1. Embed the query
        2. Search FAISS index for top-k
        3. Return chunks with similarity scores
        Returns: List of {chunk_id, document_id, text, metadata, score, similarity}
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search triggered but vector index is empty.")
            return []

        # 1. Embed query
        query_vector = embedding_service.embed_query(query)

        # 2. Search FAISS index (clamp k to size of index)
        k_search = min(k, self.index.ntotal)
        distances, indices = self.index.search(query_vector, k_search)

        results = []
        # 3. Formulate response dictionary list
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(self.metadata):
                match = self.metadata[idx]
                score = float(dist)
                # Convert L2 distance (Euclidean distance) to similarity score between 0 and 1
                similarity = 1.0 / (1.0 + score)
                
                results.append({
                    "chunk_id": match["chunk_id"],
                    "document_id": match["document_id"],
                    "text": match["text"],
                    "metadata": {
                        "filename": match["filename"],
                        "chunk_index": match["chunk_index"],
                        "total_chunks": match["total_chunks"],
                        "timestamp": match["timestamp"]
                    },
                    "score": score,
                    "similarity": similarity
                })
                
        return results

    def get_all_documents(self) -> List[str]:
        """Get list of all document IDs in the store"""
        unique_doc_ids = set(item["document_id"] for item in self.metadata)
        return list(unique_doc_ids)

# Import json for internal operations
import json

vector_store = VectorStore()
