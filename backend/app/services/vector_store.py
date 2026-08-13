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
        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)

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
                "document_id": str(chunk.get("document_id", document_id)),
                "text": chunk["text"],
                "filename": chunk["metadata"]["filename"],
                "chunk_index": chunk["metadata"].get("chunk_index", i),
                "total_chunks": chunk["metadata"].get("total_chunks", len(chunks)),
                "timestamp": chunk["metadata"].get("timestamp", "")
            })

        # 5. Save to disk
        self._save()

        return {
            "status": "success",
            "chunks_added": len(chunks)
        }

    def search(
        self,
        query: str,
        k: int = 5,
        doc_types: List[str] = None,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """Search for similar chunks with optional filtering
        Steps:
        1. Embed the query
        2. Search FAISS index for candidates
        3. Filter by doc_types and date ranges
        4. Return top-k matching chunks with similarity scores
        Returns: List of {chunk_id, document_id, text, metadata, score, similarity}
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search triggered but vector index is empty.")
            return []

        # 1. Embed query
        query_vector = embedding_service.embed_query(query)

        # Normalize doc_types if provided
        normalized_types = None
        if doc_types:
            normalized_types = set(t.lower().lstrip('.') for t in doc_types if t)

        # 2. Search FAISS index - retrieve full candidate pool when filters are present to ensure recall
        if normalized_types or start_date or end_date:
            k_search = self.index.ntotal
        else:
            k_search = min(max(k * 4, 50), self.index.ntotal)

        distances, indices = self.index.search(query_vector, k_search)

        results = []
        # 3. Formulate response dictionary list with filter application
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(self.metadata):
                match = self.metadata[idx]
                filename = match.get("filename", "")
                
                # Check doc_types filter
                if normalized_types:
                    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ""
                    if ext not in normalized_types:
                        continue

                # Check date range filter
                timestamp = match.get("timestamp", "")
                if timestamp:
                    chunk_date = timestamp[:10]  # YYYY-MM-DD
                    if start_date and chunk_date < start_date[:10]:
                        continue
                    if end_date and chunk_date > end_date[:10]:
                        continue

                score = float(dist)
                # Convert L2 distance (Euclidean distance) to similarity score between 0 and 1
                similarity = 1.0 / (1.0 + score)
                
                results.append({
                    "chunk_id": match.get("chunk_id", f"chunk_{idx}"),
                    "document_id": str(match.get("document_id", "")),
                    "text": match.get("text", ""),
                    "metadata": {
                        "filename": filename,
                        "chunk_index": match.get("chunk_index", 0),
                        "total_chunks": match.get("total_chunks", 1),
                        "timestamp": timestamp,
                        "doc_type": filename.rsplit('.', 1)[-1].lower() if '.' in filename else "txt"
                    },
                    "score": score,
                    "similarity": round(similarity, 4)
                })

                if len(results) >= k:
                    break
                
        return results

    def get_related_chunks(self, document_id: str, current_chunk_id: str, limit: int = 2) -> List[Dict[str, Any]]:
        """Retrieve related/adjacent chunks from the same document for context expansion."""
        doc_chunks = [m for m in self.metadata if str(m.get("document_id")) == str(document_id)]
        if not doc_chunks:
            return []

        # Find current chunk index
        curr_meta = next((m for m in doc_chunks if m.get("chunk_id") == current_chunk_id), None)
        current_idx = curr_meta.get("chunk_index", 0) if curr_meta else -1

        related = []
        
        # Priority 1: Adjacent chunks (chunk_index - 1 or chunk_index + 1)
        if current_idx >= 0:
            adjacent = [
                m for m in doc_chunks 
                if m.get("chunk_id") != current_chunk_id and abs(m.get("chunk_index", -99) - current_idx) == 1
            ]
            for m in adjacent:
                related.append({
                    "chunk_id": m.get("chunk_id", ""),
                    "chunk_index": m.get("chunk_index", 0),
                    "text": m.get("text", ""),
                    "similarity": 0.95
                })
                if len(related) >= limit:
                    break

        # Priority 2: Other chunks from same document if adjacent count is below limit
        if len(related) < limit:
            for m in doc_chunks:
                if m.get("chunk_id") != current_chunk_id and m.get("chunk_id") not in [r["chunk_id"] for r in related]:
                    related.append({
                        "chunk_id": m.get("chunk_id", ""),
                        "chunk_index": m.get("chunk_index", 0),
                        "text": m.get("text", ""),
                        "similarity": 0.85
                    })
                    if len(related) >= limit:
                        break

        return related

    def get_all_documents(self) -> List[str]:
        """Get list of all document IDs in the store"""
        unique_doc_ids = set(item["document_id"] for item in self.metadata)
        return list(unique_doc_ids)

vector_store = VectorStore()
