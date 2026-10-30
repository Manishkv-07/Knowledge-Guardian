import os
import json
import re
from typing import List, Dict, Any, Optional
import numpy as np
import faiss

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

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
        self.bm25 = None    # Lexical BM25 index over chunk texts

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

        # Build or synchronize BM25 lexical index with current metadata
        self._rebuild_bm25()

    def _rebuild_bm25(self):
        """Constructs an in-memory BM25 index over all indexed text chunks."""
        if not BM25_AVAILABLE or not self.metadata:
            self.bm25 = None
            return

        try:
            tokenized_corpus = []
            for item in self.metadata:
                text = item.get("text", "")
                tokens = re.findall(r'\b[a-zA-Z0-9_-]+\b', text.lower())
                tokenized_corpus.append(tokens)

            if tokenized_corpus:
                self.bm25 = BM25Okapi(tokenized_corpus)
                logger.info(f"Synchronized BM25 lexical index with {len(tokenized_corpus)} chunks.")
            else:
                self.bm25 = None
        except Exception as e:
            logger.error(f"Failed to build BM25 lexical index: {e}")
            self.bm25 = None

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
                "page_number": chunk["metadata"].get("page_number"),
                "chunk_index": chunk["metadata"].get("chunk_index", i),
                "total_chunks": chunk["metadata"].get("total_chunks", len(chunks)),
                "timestamp": chunk["metadata"].get("timestamp", "")
            })

        # 5. Save to disk
        self._save()
        self._rebuild_bm25()

        return {
            "status": "success",
            "chunks_added": len(chunks)
        }

    def delete_document(self, document_id: str) -> dict:
        """Removes all vectors and metadata associated with a document_id.
        
        Synchronizes the FAISS index with metadata and persists changes to disk.
        Properly handles deleting one document, multiple chunks, or the last document.
        """
        doc_id_str = str(document_id)
        if self.index is None or len(self.metadata) == 0:
            return {"status": "success", "chunks_deleted": 0, "remaining_chunks": 0}

        remove_indices = []
        new_metadata = []
        for i, meta in enumerate(self.metadata):
            if str(meta.get("document_id")) == doc_id_str:
                remove_indices.append(i)
            else:
                new_metadata.append(meta)

        if not remove_indices:
            logger.info(f"No vectors found in index for document {doc_id_str}")
            return {"status": "success", "chunks_deleted": 0, "remaining_chunks": len(self.metadata)}

        num_to_remove = len(remove_indices)
        logger.info(f"Purging {num_to_remove} vector(s) for document ID '{doc_id_str}' from FAISS...")

        # If all items are being removed, reset index to a fresh empty IndexFlatL2
        if len(new_metadata) == 0:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
        else:
            # Remove vectors matching the indices
            sel = faiss.IDSelectorBatch(np.array(remove_indices, dtype=np.int64))
            self.index.remove_ids(sel)
            self.metadata = new_metadata

        # Persist synchronized index and metadata to disk
        self._save()
        self._rebuild_bm25()

        logger.info(f"Successfully deleted document '{doc_id_str}'. Remaining vectors in FAISS: {self.index.ntotal}")
        return {
            "status": "success",
            "chunks_deleted": num_to_remove,
            "remaining_chunks": len(self.metadata)
        }

    def delete_documents(self, document_ids: List[str]) -> dict:
        """Purge multiple documents in a single atomic vector operation."""
        target_ids = {str(d) for d in document_ids}
        if self.index is None or len(self.metadata) == 0:
            return {"status": "success", "chunks_deleted": 0, "remaining_chunks": 0}

        remove_indices = []
        new_metadata = []
        for i, meta in enumerate(self.metadata):
            if str(meta.get("document_id")) in target_ids:
                remove_indices.append(i)
            else:
                new_metadata.append(meta)

        if not remove_indices:
            return {"status": "success", "chunks_deleted": 0, "remaining_chunks": len(self.metadata)}

        num_to_remove = len(remove_indices)
        if len(new_metadata) == 0:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
        else:
            sel = faiss.IDSelectorBatch(np.array(remove_indices, dtype=np.int64))
            self.index.remove_ids(sel)
            self.metadata = new_metadata

        self._save()
        self._rebuild_bm25()
        return {
            "status": "success",
            "chunks_deleted": num_to_remove,
            "remaining_chunks": len(self.metadata)
        }

    def rebuild_index(self) -> dict:
        """Rebuild the entire FAISS index and metadata from all persisted chunk files.
        
        Scans data/chunks/*.json, extracts texts, generates unit-normalized embeddings,
        reconstructs the FAISS index from scratch, and persists to disk.
        """
        chunks_dir = BASE_DIR / settings.CHUNK_DIR
        if not chunks_dir.exists():
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            self._save()
            return {"status": "success", "documents_indexed": 0, "chunks_indexed": 0}

        chunk_files = list(chunks_dir.glob("*.json"))
        logger.info(f"Rebuilding vector index from {len(chunk_files)} chunk files in {chunks_dir}...")

        new_index = faiss.IndexFlatL2(self.dimension)
        new_metadata = []
        total_chunks = 0
        docs_indexed = 0

        for chunk_file in chunk_files:
            try:
                with open(chunk_file, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
                if not chunks:
                    continue

                texts = [c["text"] for c in chunks]
                embeddings = embedding_service.embed_texts(texts)
                new_index.add(embeddings)

                doc_id = chunk_file.stem
                for i, chunk in enumerate(chunks):
                    new_metadata.append({
                        "chunk_id": chunk.get("id", f"{doc_id}_{i}"),
                        "document_id": str(chunk.get("document_id", doc_id)),
                        "text": chunk.get("text", ""),
                        "filename": chunk.get("metadata", {}).get("filename", chunk_file.name),
                        "page_number": chunk.get("metadata", {}).get("page_number"),
                        "chunk_index": chunk.get("metadata", {}).get("chunk_index", i),
                        "total_chunks": chunk.get("metadata", {}).get("total_chunks", len(chunks)),
                        "timestamp": chunk.get("metadata", {}).get("timestamp", "")
                    })
                total_chunks += len(chunks)
                docs_indexed += 1
            except Exception as e:
                logger.error(f"Failed to read chunk file {chunk_file} during rebuild: {e}")

        self.index = new_index
        self.metadata = new_metadata
        self._save()
        self._rebuild_bm25()
        logger.info(f"Vector index rebuild complete. {docs_indexed} documents, {total_chunks} chunks indexed.")
        return {
            "status": "success",
            "documents_indexed": docs_indexed,
            "chunks_indexed": total_chunks
        }

    def search(
        self,
        query: str,
        k: int = 5,
        doc_types: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        hybrid: bool = True
    ) -> List[Dict]:
        """Search for similar chunks with optional filtering and hybrid (FAISS + BM25) ranking.
        
        When hybrid=True and BM25 is available, combines dense FAISS vector search with
        BM25 lexical retrieval using Reciprocal Rank Fusion (RRF, k=60).
        """
        if self.index is None or self.index.ntotal == 0 or len(self.metadata) == 0:
            logger.warning("Search triggered but vector index is empty.")
            return []

        if not query or not query.strip():
            logger.warning("Search triggered with empty or whitespace query.")
            return []

        # Normalize doc_types if provided
        normalized_types = None
        if doc_types:
            normalized_types = set(t.lower().lstrip('.') for t in doc_types if t)

        # 1. Dense FAISS candidate retrieval
        query_vector = embedding_service.embed_query(query)
        if normalized_types or start_date or end_date:
            k_dense_search = self.index.ntotal
        else:
            k_dense_search = min(max(k * 4, 50), self.index.ntotal)

        distances, indices = self.index.search(query_vector, k_dense_search)

        dense_ranks = {}
        dense_distances = {}
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), 1):
            if 0 <= idx < len(self.metadata):
                dense_ranks[idx] = rank
                dense_distances[idx] = float(dist)

        # 2. Lexical BM25 candidate retrieval
        lexical_ranks = {}
        lexical_scores = {}
        if hybrid and self.bm25 is not None:
            try:
                q_tokens = re.findall(r'\b[a-zA-Z0-9_-]+\b', query.lower())
                if q_tokens:
                    bm25_scores = self.bm25.get_scores(q_tokens)
                    scored_candidates = [
                        (idx, float(score))
                        for idx, score in enumerate(bm25_scores)
                        if score > 0 and 0 <= idx < len(self.metadata)
                    ]
                    scored_candidates.sort(key=lambda x: x[1], reverse=True)
                    for rank, (idx, score) in enumerate(scored_candidates[:k_dense_search], 1):
                        lexical_ranks[idx] = rank
                        lexical_scores[idx] = score
            except Exception as e:
                logger.warning(f"BM25 lexical scoring error: {e}. Falling back to pure dense search.")
                lexical_ranks = {}

        # 3. Candidate Fusion via Reciprocal Rank Fusion (RRF)
        rrf_k = 60
        if hybrid and lexical_ranks:
            all_candidate_indices = set(dense_ranks.keys()).union(set(lexical_ranks.keys()))
            scored_pool = []
            for idx in all_candidate_indices:
                d_rank = dense_ranks.get(idx, 1000)
                l_rank = lexical_ranks.get(idx, 1000)
                rrf_score = (1.0 / (rrf_k + d_rank)) + (1.0 / (rrf_k + l_rank))
                scored_pool.append((idx, rrf_score))
            scored_pool.sort(key=lambda x: x[1], reverse=True)
            candidate_indices = [idx for idx, _ in scored_pool]
            rrf_dict = dict(scored_pool)
        else:
            candidate_indices = list(dense_ranks.keys())
            rrf_dict = {}

        # 4. Formulate response dictionary list with filter application & deduplication
        results = []
        seen_chunk_ids = set()

        for idx in candidate_indices:
            if not (0 <= idx < len(self.metadata)):
                continue

            match = self.metadata[idx]
            chunk_id = match.get("chunk_id", f"chunk_{idx}")
            if chunk_id in seen_chunk_ids:
                continue

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

            # Compute score and similarity
            if idx in dense_distances:
                score = dense_distances[idx]
            else:
                try:
                    vec = self.index.reconstruct(int(idx))
                    score = float(np.sum((query_vector[0] - vec) ** 2))
                except Exception:
                    score = 2.0  # neutral distance

            similarity = max(0.0, min(1.0, 1.0 - (score / 2.0)))

            item = {
                "chunk_id": chunk_id,
                "text": match.get("text", ""),
                "document_id": str(match.get("document_id", "")),
                "filename": filename,
                "page_number": match.get("page_number"),
                "chunk_index": match.get("chunk_index", 0),
                "similarity": round(similarity, 4),
                "score": score,
                "rrf_score": round(rrf_dict.get(idx, 0.0), 6) if rrf_dict else None,
                "metadata": {
                    "filename": filename,
                    "page_number": match.get("page_number"),
                    "chunk_index": match.get("chunk_index", 0),
                    "total_chunks": match.get("total_chunks", 1),
                    "timestamp": timestamp,
                    "doc_type": filename.rsplit('.', 1)[-1].lower() if '.' in filename else "txt"
                }
            }
            results.append(item)
            seen_chunk_ids.add(chunk_id)

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
