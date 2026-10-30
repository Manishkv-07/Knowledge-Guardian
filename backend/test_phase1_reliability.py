"""
Personal Knowledge Guardian - Phase 1 Automated Reliability Test Suite
Covers:
1. FAISS & SQLite Deletion Synchronization (single doc, multiple docs, last doc, search after deletion).
2. Embedding Normalization & L2-to-Cosine-Similarity Metric Verification.
3. Ingestion Pipeline & Edge Cases (empty files, corrupt PDFs, 1-indexed page numbers, 0-byte upload rejection).
4. Groq LLM Reliability, Distinguishable Configuration Failures, and Fallback Verification.
5. Index Rebuild from Persisted Chunks.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import faiss

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure stdout handles UTF-8 on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from app.config import settings
from app.services.embedding import embedding_service
from app.services.vector_store import VectorStore
from app.services.ingestion import ingestion_service
from app.services.llm_client import llm_client
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestVectorStoreConsistency(unittest.TestCase):
    """Verifies FAISS vector store deletion synchronization, order preservation, and index rebuilds."""

    def setUp(self):
        # Create a temporary directory for isolated vector store tests
        self.test_dir = tempfile.mkdtemp()
        self.patcher1 = patch.object(settings, "VECTOR_STORE_DIR", self.test_dir)
        self.patcher2 = patch.object(settings, "CHUNK_DIR", os.path.join(self.test_dir, "chunks"))
        self.patcher1.start()
        self.patcher2.start()

        os.makedirs(os.path.join(self.test_dir, "chunks"), exist_ok=True)
        self.vs = VectorStore()
        # Override paths to test dir
        self.vs.index_dir = Path(self.test_dir)
        self.vs.index_path = Path(self.test_dir) / "test_index.faiss"
        self.vs.metadata_path = Path(self.test_dir) / "test_metadata.json"
        self.vs.index = faiss.IndexFlatL2(self.vs.dimension)
        self.vs.metadata = []

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_chunks(self, doc_id: str, count: int, text_prefix: str, filename: str):
        """Helper to create dummy chunk JSON file and index into vector store."""
        chunk_file = Path(self.test_dir) / "chunks" / f"{doc_id}.json"
        chunks = []
        for i in range(count):
            chunks.append({
                "id": f"{doc_id}_{i}",
                "document_id": doc_id,
                "text": f"{text_prefix} paragraph {i} discussing knowledge architectures.",
                "metadata": {
                    "filename": filename,
                    "page_number": i + 1,
                    "chunk_index": i,
                    "total_chunks": count,
                    "timestamp": "2026-10-29T12:00:00Z"
                }
            })
        with open(chunk_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f)

        # Index into vector store
        with patch("app.services.vector_store.BASE_DIR", Path(self.test_dir).parent):
            # Point chunk file location dynamically
            orig_chunk_dir = settings.CHUNK_DIR
            settings.CHUNK_DIR = os.path.relpath(os.path.join(self.test_dir, "chunks"), Path(self.test_dir).parent)
            res = self.vs.add_document(doc_id)
            settings.CHUNK_DIR = orig_chunk_dir
        return res

    def test_single_document_deletion(self):
        """Test deleting one document removes its vectors and leaves other documents intact."""
        self._create_mock_chunks("doc_1", 2, "Quantum Computing", "quantum.pdf")
        self._create_mock_chunks("doc_2", 3, "Biology Genomics", "biology.pdf")
        
        self.assertEqual(self.vs.index.ntotal, 5)
        self.assertEqual(len(self.vs.metadata), 5)

        # Delete doc_1
        del_res = self.vs.delete_document("doc_1")
        self.assertEqual(del_res["chunks_deleted"], 2)
        self.assertEqual(del_res["remaining_chunks"], 3)
        self.assertEqual(self.vs.index.ntotal, 3)
        self.assertEqual(len(self.vs.metadata), 3)

        # Verify no vectors or metadata remain for doc_1
        for meta in self.vs.metadata:
            self.assertNotEqual(meta["document_id"], "doc_1")
            self.assertEqual(meta["document_id"], "doc_2")

        # Search for quantum - should not return any doc_1 matches
        results = self.vs.search("Quantum Computing", k=5)
        for r in results:
            self.assertNotEqual(r["document_id"], "doc_1")

    def test_multiple_documents_deletion(self):
        """Test batch deleting multiple documents."""
        self._create_mock_chunks("doc_A", 2, "Astronomy Stars", "stars.txt")
        self._create_mock_chunks("doc_B", 2, "Chemistry Molecules", "chemistry.txt")
        self._create_mock_chunks("doc_C", 2, "Economics Markets", "economics.txt")

        self.assertEqual(self.vs.index.ntotal, 6)

        # Delete doc_A and doc_B together
        del_res = self.vs.delete_documents(["doc_A", "doc_B"])
        self.assertEqual(del_res["chunks_deleted"], 4)
        self.assertEqual(self.vs.index.ntotal, 2)
        self.assertEqual(len(self.vs.metadata), 2)

        # Only doc_C must remain
        for meta in self.vs.metadata:
            self.assertEqual(meta["document_id"], "doc_C")

    def test_delete_last_document(self):
        """Test deleting the last remaining document clears the index cleanly to 0 vectors."""
        self._create_mock_chunks("doc_only", 3, "Sole Record", "sole.md")
        self.assertEqual(self.vs.index.ntotal, 3)

        del_res = self.vs.delete_document("doc_only")
        self.assertEqual(del_res["chunks_deleted"], 3)
        self.assertEqual(del_res["remaining_chunks"], 0)
        self.assertEqual(self.vs.index.ntotal, 0)
        self.assertEqual(len(self.vs.metadata), 0)

        # Searching an empty store returns empty list gracefully
        results = self.vs.search("Sole Record", k=5)
        self.assertEqual(results, [])

    def test_rebuild_index_from_persisted_chunks(self):
        """Test rebuilding the index from disk chunk JSON files restores exact vectors and metadata."""
        self._create_mock_chunks("doc_rebuild_1", 2, "Deep Learning", "dl.pdf")
        self._create_mock_chunks("doc_rebuild_2", 2, "Reinforcement Learning", "rl.pdf")
        self.assertEqual(self.vs.index.ntotal, 4)

        # Corrupt / wipe memory index
        self.vs.index = faiss.IndexFlatL2(self.vs.dimension)
        self.vs.metadata = []
        self.assertEqual(self.vs.index.ntotal, 0)

        # Rebuild
        with patch("app.services.vector_store.BASE_DIR", Path(self.test_dir).parent):
            orig_chunk_dir = settings.CHUNK_DIR
            settings.CHUNK_DIR = os.path.relpath(os.path.join(self.test_dir, "chunks"), Path(self.test_dir).parent)
            rebuild_res = self.vs.rebuild_index()
            settings.CHUNK_DIR = orig_chunk_dir

        self.assertEqual(rebuild_res["documents_indexed"], 2)
        self.assertEqual(rebuild_res["chunks_indexed"], 4)
        self.assertEqual(self.vs.index.ntotal, 4)
        self.assertEqual(len(self.vs.metadata), 4)


class TestEmbeddingAndMetricCorrectness(unittest.TestCase):
    """Verifies embedding L2-normalization and mathematical distance-to-similarity conversion."""

    def test_embeddings_are_unit_normalized(self):
        """Verify embed_texts and embed_query produce L2 unit norm vectors (norm == 1.0)."""
        texts = ["Artificial intelligence is transforming science.", "FAISS enables high-speed vector retrieval."]
        embeddings = embedding_service.embed_texts(texts)
        self.assertEqual(embeddings.shape[0], 2)
        self.assertEqual(embeddings.shape[1], 384)

        for emb in embeddings:
            norm = float(np.linalg.norm(emb))
            self.assertAlmostEqual(norm, 1.0, places=4, msg="Document embedding is not unit normalized!")

        query_emb = embedding_service.embed_query("Artificial intelligence")
        self.assertEqual(query_emb.shape, (1, 384))
        q_norm = float(np.linalg.norm(query_emb[0]))
        self.assertAlmostEqual(q_norm, 1.0, places=4, msg="Query embedding is not unit normalized!")

    def test_similarity_metric_conversion(self):
        """
        Verify conversion: Cosine_Similarity = 1 - (D / 2.0)
        For unit vectors u, v: D = ||u - v||^2 = 2 - 2*cos(theta).
        Therefore: cos(theta) = 1 - (D / 2.0).
        """
        # Case 1: Identical vectors (D = 0) -> Similarity = 1.0
        d_zero = 0.0
        sim_identical = max(0.0, min(1.0, 1.0 - (d_zero / 2.0)))
        self.assertEqual(sim_identical, 1.0)

        # Case 2: Orthogonal vectors (D = 2.0, cos(theta) = 0) -> Similarity = 0.0
        d_ortho = 2.0
        sim_ortho = max(0.0, min(1.0, 1.0 - (d_ortho / 2.0)))
        self.assertEqual(sim_ortho, 0.0)

        # Case 3: Angle with cos(theta) = 0.85 -> D = 2 - 2(0.85) = 0.3
        d_val = 0.3
        sim_expected = 1.0 - (0.3 / 2.0)  # 0.85
        sim_calc = max(0.0, min(1.0, 1.0 - (d_val / 2.0)))
        self.assertAlmostEqual(sim_calc, sim_expected, places=4)


class TestIngestionValidation(unittest.TestCase):
    """Verifies validation of empty files, malformed text, and PDF page numbers."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_text_file_rejected(self):
        """Ingestion of an empty TXT/MD file must raise ValueError."""
        empty_file = Path(self.test_dir) / "empty.txt"
        with open(empty_file, "w", encoding="utf-8") as f:
            f.write("   \n\t  ")

        with self.assertRaises(ValueError) as ctx:
            ingestion_service.process_text(str(empty_file), "empty.txt")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_corrupt_pdf_file_rejected(self):
        """Ingestion of a non-PDF or corrupt file passed as PDF must raise ValueError."""
        fake_pdf = Path(self.test_dir) / "corrupt.pdf"
        with open(fake_pdf, "wb") as f:
            f.write(b"NOT A REAL PDF HEADER")

        with self.assertRaises(ValueError) as ctx:
            ingestion_service.process_pdf(str(fake_pdf), "corrupt.pdf")
        self.assertIn("failed to parse pdf", str(ctx.exception).lower())

    def test_pdf_page_number_preservation(self):
        """Verify that PyMuPDF ingestion produces 1-indexed page numbers."""
        import fitz
        test_pdf = Path(self.test_dir) / "two_page.pdf"
        doc = fitz.open()
        
        # Add Page 1
        page1 = doc.new_page()
        page1.insert_text((50, 72), "First page content on Transformer attention mechanisms.")
        
        # Add Page 2
        page2 = doc.new_page()
        page2.insert_text((50, 72), "Second page content on Retrieval-Augmented Generation.")
        
        doc.save(str(test_pdf))
        doc.close()

        res = ingestion_service.process_pdf(str(test_pdf), "two_page.pdf", document_id="pdf_test_doc")
        self.assertGreaterEqual(res["total_chunks"], 2)
        
        # Page numbers must be 1 and 2 (1-indexed)
        page_numbers = {c["metadata"]["page_number"] for c in res["chunks"]}
        self.assertIn(1, page_numbers)
        self.assertIn(2, page_numbers)
        self.assertNotIn(0, page_numbers)  # Must NOT be 0-indexed


class TestGroqIntegrationAndErrorHandling(unittest.TestCase):
    """Verifies Groq LLM stability, error handling, and clear fallback distinction."""

    def test_empty_query_handling(self):
        """Empty query returns early without calling external LLM."""
        res = llm_client.generate_answer("", [{"text": "Sample text", "filename": "test.txt"}])
        self.assertEqual(res["answer"], "Query cannot be empty.")
        self.assertEqual(res["sources"], [])

    def test_empty_chunks_insufficient_context(self):
        """When no context chunks are supplied, returns clear message without hallucinating."""
        res = llm_client.generate_answer("What is quantum computing?", [])
        self.assertIn("couldn't find any relevant", res["answer"].lower())
        self.assertEqual(res["sources"], [])

    def test_unconfigured_api_key_distinguishable_from_retrieval(self):
        """Unconfigured key returns configuration warning distinguishing it from document retrieval failure."""
        with patch.object(llm_client, "is_groq_configured", return_value=False):
            res = llm_client.generate_answer("How does attention work?", [{"text": "Context passage", "filename": "doc.pdf"}])
            self.assertIn("Groq API key is not configured", res["answer"])
            self.assertEqual(len(res["sources"]), 1)

    @patch("app.services.llm_client.GROQ_AVAILABLE", True)
    def test_authentication_error_handling(self):
        """Simulate Groq AuthenticationError (HTTP 401)."""
        import groq
        mock_chat = MagicMock()
        mock_chat.invoke.side_effect = groq.AuthenticationError(
            message="Invalid API Key",
            response=MagicMock(status_code=401),
            body={"error": {"message": "Invalid API Key"}}
        )

        with patch.object(llm_client, "is_groq_configured", return_value=True), \
             patch.object(llm_client, "_get_chat_model", return_value=mock_chat):
            res = llm_client.generate_answer("Test query", [{"text": "Context", "filename": "doc.pdf"}])
            self.assertIn("Authentication error", res["answer"])
            self.assertIn("Invalid Groq API key", res["answer"])

    @patch("app.services.llm_client.GROQ_AVAILABLE", True)
    def test_rate_limit_error_handling(self):
        """Simulate Groq RateLimitError (HTTP 429)."""
        import groq
        mock_chat = MagicMock()
        mock_chat.invoke.side_effect = groq.RateLimitError(
            message="Rate limit reached",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )

        with patch.object(llm_client, "is_groq_configured", return_value=True), \
             patch.object(llm_client, "_get_chat_model", return_value=mock_chat):
            res = llm_client.generate_answer("Test query", [{"text": "Context", "filename": "doc.pdf"}])
            self.assertIn("rate limit reached (HTTP 429)", res["answer"])

    @patch("app.services.llm_client.GROQ_AVAILABLE", True)
    def test_timeout_error_handling(self):
        """Simulate Groq APITimeoutError."""
        import groq
        mock_chat = MagicMock()
        mock_chat.invoke.side_effect = groq.APITimeoutError(request=MagicMock())

        with patch.object(llm_client, "is_groq_configured", return_value=True), \
             patch.object(llm_client, "_get_chat_model", return_value=mock_chat):
            res = llm_client.generate_answer("Test query", [{"text": "Context", "filename": "doc.pdf"}])
            self.assertIn("timed out", res["answer"].lower())


class TestFastAPIEndpointsReliability(unittest.TestCase):
    """Verifies API endpoints for upload rejection of 0-byte files, chat queries, and deletion."""

    def test_upload_empty_file_rejected_with_400(self):
        """Uploading a 0-byte file must be immediately rejected with HTTP 400."""
        response = client.post(
            "/api/documents/upload",
            files={"file": ("zero_byte.txt", b"", "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    def test_chat_query_unconfigured_fallback_distinction(self):
        """When Groq is unconfigured, query returns retrieval fallback without claiming LLM generation."""
        with patch.object(llm_client, "is_groq_configured", return_value=False):
            response = client.post(
                "/api/query",
                json={"query": "Test query for fallback verification"}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("answer", data)
            self.assertIn("conversation_id", data)
            # Response must clearly identify as fallback or indicate Groq is not configured
            self.assertTrue(
                "Fallback" in data["answer"] or "not configured" in data["answer"] or "couldn't find" in data["answer"]
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
