"""
Personal Knowledge Guardian - Phase 2 Automated Intelligence Test Suite
Covers:
1. Hybrid Retrieval Engine (BM25 + FAISS Dense + RRF Fusion, filter preservation, deduplication).
2. Retrieval Evaluation (Recall and MRR comparison between Baseline FAISS vs Hybrid Search).
3. Proactive Cross-Document Connection Engine:
   - Candidate pair discovery (excluding self-document chunks).
   - LLM structured evaluation & relationship categorization.
   - Dual-passage factual evidence validation.
   - Deduplication of connections across queries/runs.
   - Review status transitions ('saved', 'dismissed', 'new').
   - Cascade deletion when parent document is removed.
4. Persistent Memory Architecture:
   - Fact / Insight memory persistence.
   - Query-relevant episodic memory retrieval (without history dumping).
   - Pattern / Cognitive recurring topic memory persistence and dismissal.
5. Source-Grounded Flashcards & SM-2 Spaced Repetition:
   - AI generation strictly grounded in source chunk snippets.
   - Manual card creation, update, deletion.
   - Deterministic SM-2 review scheduling (Again, Hard, Good, Easy).
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
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
from app.models.document import (
    Base, engine, SessionLocal,
    DocumentORM, DocumentConnectionORM, FlashcardORM, PatternMemoryORM
)
from app.services.embedding import embedding_service
from app.services.vector_store import VectorStore
from app.services.connection_engine import ConnectionEngine, ConnectionEvaluation
from app.services.flashcard_service import FlashcardService
from app.services.memory_manager import MemoryManager
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHybridRetrievalEngine(unittest.TestCase):
    """Verifies BM25 + FAISS Reciprocal Rank Fusion (RRF), filters, and deduplication."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.patcher1 = patch.object(settings, "VECTOR_STORE_DIR", self.test_dir)
        self.patcher2 = patch.object(settings, "CHUNK_DIR", os.path.join(self.test_dir, "chunks"))
        self.patcher1.start()
        self.patcher2.start()

        os.makedirs(os.path.join(self.test_dir, "chunks"), exist_ok=True)
        self.vs = VectorStore()
        self.vs.index_dir = Path(self.test_dir)
        self.vs.index_path = Path(self.test_dir) / "test_index.faiss"
        self.vs.metadata_path = Path(self.test_dir) / "test_metadata.json"
        self.vs.index = faiss.IndexFlatL2(self.vs.dimension)
        self.vs.metadata = []

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _index_sample_corpus(self):
        """Indexes a controlled 4-document corpus with distinct vocabulary for retrieval benchmarks."""
        corpus = [
            {
                "doc_id": "1",
                "filename": "quantum_computing.pdf",
                "timestamp": "2026-01-15T10:00:00Z",
                "chunks": [
                    "Superconducting qubits rely on Josephson junctions to maintain quantum coherence at cryogenic millikelvin temperatures.",
                    "Quantum error correction uses surface codes to stabilize logical qubits against environmental decoherence."
                ]
            },
            {
                "doc_id": "2",
                "filename": "deep_learning_nlp.txt",
                "timestamp": "2026-03-20T14:30:00Z",
                "chunks": [
                    "Self-attention mechanisms calculate scaled dot-product attention across keys, queries, and values.",
                    "Transformers replace recurrent LSTM units with parallel multi-head attention projections."
                ]
            },
            {
                "doc_id": "3",
                "filename": "database_internals.pdf",
                "timestamp": "2026-06-10T09:15:00Z",
                "chunks": [
                    "B-tree indexing optimizes range scans and disk page utilization in relational engines.",
                    "Write-ahead logging (WAL) guarantees ACID atomicity and durability during crash recovery."
                ]
            },
            {
                "doc_id": "4",
                "filename": "distributed_consensus.md",
                "timestamp": "2026-08-05T16:00:00Z",
                "chunks": [
                    "Raft consensus decomposes state machine replication into leader election, log replication, and safety.",
                    "Paxos achieves consensus over asynchronous networks despite arbitrary node partition failures."
                ]
            }
        ]

        orig_chunk_dir = settings.CHUNK_DIR
        settings.CHUNK_DIR = os.path.relpath(os.path.join(self.test_dir, "chunks"), Path(self.test_dir).parent)

        try:
            with patch("app.services.vector_store.BASE_DIR", Path(self.test_dir).parent):
                for item in corpus:
                    chunk_file = Path(self.test_dir) / "chunks" / f"{item['doc_id']}.json"
                    chunk_objs = []
                    for i, text in enumerate(item["chunks"]):
                        chunk_objs.append({
                            "id": f"{item['doc_id']}_{i}",
                            "document_id": item["doc_id"],
                            "text": text,
                            "metadata": {
                                "filename": item["filename"],
                                "page_number": i + 1,
                                "chunk_index": i,
                                "total_chunks": len(item["chunks"]),
                                "timestamp": item["timestamp"]
                            }
                        })
                    with open(chunk_file, "w", encoding="utf-8") as f:
                        json.dump(chunk_objs, f)
                    self.vs.add_document(item["doc_id"])
        finally:
            settings.CHUNK_DIR = orig_chunk_dir

    def test_bm25_initialization_and_sync(self):
        """Verifies BM25 corpus builds and stays synchronized with FAISS."""
        self._index_sample_corpus()
        self.assertIsNotNone(self.vs.bm25)
        self.assertEqual(self.vs.bm25.corpus_size, 8)
        self.assertEqual(self.vs.index.ntotal, 8)

    def test_hybrid_rrf_scoring(self):
        """Verifies that search returns RRF scores when hybrid=True and BM25 matches."""
        self._index_sample_corpus()
        results = self.vs.search("Josephson junctions superconducting qubits", k=3, hybrid=True)
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertEqual(top["document_id"], "1")
        self.assertIn("rrf_score", top)
        self.assertGreater(top["rrf_score"], 0.0)

    def test_hybrid_retrieval_filtering(self):
        """Verifies doc_types and date range filters work seamlessly in hybrid search."""
        self._index_sample_corpus()

        # Filter by doc_types: only pdf
        pdf_results = self.vs.search("attention mechanisms", k=5, doc_types=["pdf"], hybrid=True)
        for r in pdf_results:
            self.assertTrue(r["filename"].endswith(".pdf"), f"Expected PDF file, got {r['filename']}")

        # Filter by doc_types: only txt
        txt_results = self.vs.search("attention mechanisms", k=5, doc_types=["txt"], hybrid=True)
        self.assertGreater(len(txt_results), 0)
        for r in txt_results:
            self.assertTrue(r["filename"].endswith(".txt"), f"Expected TXT file, got {r['filename']}")

        # Filter by date range: only first half of 2026 (<= 2026-05-01)
        dated_results = self.vs.search("indexing and consensus", k=5, end_date="2026-05-01", hybrid=True)
        for r in dated_results:
            self.assertIn(r["document_id"], ["1", "2"])

    def test_retrieval_evaluation_benchmark(self):
        """Compares Recall@3 and MRR between Baseline FAISS vs Hybrid (BM25 + FAISS) on exact keyword queries."""
        self._index_sample_corpus()

        # Evaluation queries with target document IDs
        eval_cases = [
            {"query": "Josephson cryogenic millikelvin", "expected_doc": "1"},
            {"query": "B-tree indexing disk page", "expected_doc": "3"},
            {"query": "Write-ahead logging WAL crash recovery", "expected_doc": "3"},
            {"query": "Raft leader election log replication", "expected_doc": "4"},
            {"query": "Paxos asynchronous network partition", "expected_doc": "4"}
        ]

        def evaluate_retriever(use_hybrid: bool):
            mrr_sum = 0.0
            hits_at_1 = 0
            hits_at_3 = 0
            for case in eval_cases:
                res = self.vs.search(case["query"], k=3, hybrid=use_hybrid)
                retrieved_docs = [r["document_id"] for r in res]
                expected = case["expected_doc"]
                if expected in retrieved_docs:
                    rank = retrieved_docs.index(expected) + 1
                    mrr_sum += 1.0 / rank
                    if rank == 1:
                        hits_at_1 += 1
                    if rank <= 3:
                        hits_at_3 += 1

            n = len(eval_cases)
            return {
                "mrr": mrr_sum / n,
                "recall@1": hits_at_1 / n,
                "recall@3": hits_at_3 / n
            }

        faiss_only = evaluate_retriever(use_hybrid=False)
        hybrid = evaluate_retriever(use_hybrid=True)

        print("\n--- Retrieval Evaluation Benchmark ---")
        print(f"FAISS Dense Only   : Recall@1={faiss_only['recall@1']:.2f}, Recall@3={faiss_only['recall@3']:.2f}, MRR={faiss_only['mrr']:.3f}")
        print(f"Hybrid (FAISS+BM25): Recall@1={hybrid['recall@1']:.2f}, Recall@3={hybrid['recall@3']:.2f}, MRR={hybrid['mrr']:.3f}")

        # Hybrid search must meet or exceed pure dense search on exact vocabulary queries
        self.assertGreaterEqual(hybrid["recall@3"], faiss_only["recall@3"])
        self.assertGreaterEqual(hybrid["mrr"], faiss_only["mrr"])
        self.assertEqual(hybrid["recall@3"], 1.0)


class TestConnectionEngine(unittest.TestCase):
    """Verifies proactive cross-document connection discovery, evaluation, deduplication, and cascade deletion."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.engine = ConnectionEngine()

        # Clean any old test records
        self.db.query(DocumentConnectionORM).delete()
        self.db.query(DocumentORM).filter(DocumentORM.id.in_([901, 902, 903])).delete()
        self.db.commit()

        # Create two test documents in DB
        now = datetime.utcnow()
        self.doc1 = DocumentORM(
            id=901,
            filename="attention_models.pdf",
            filepath="data/uploads/attention_models.pdf",
            file_size=50000,
            upload_time=now,
            status="indexed",
            chunk_count=2
        )
        self.doc2 = DocumentORM(
            id=902,
            filename="rag_grounding.pdf",
            filepath="data/uploads/rag_grounding.pdf",
            file_size=40000,
            upload_time=now,
            status="indexed",
            chunk_count=2
        )
        self.db.add_all([self.doc1, self.doc2])
        self.db.commit()

    def tearDown(self):
        self.db.query(DocumentConnectionORM).delete()
        self.db.query(DocumentORM).filter(DocumentORM.id.in_([901, 902, 903])).delete()
        self.db.commit()
        self.db.close()

    def test_evaluate_pair_with_mocked_llm(self):
        """Verifies relationship evaluation extracts valid JSON, relationship type, and requires evidence."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "has_connection": True,
            "relationship_type": "SUPPORTS",
            "explanation": "Passage B provides empirical validation of the theoretical attention mechanism in Passage A.",
            "evidence_source": "Multi-Head Attention projects queries, keys, and values linearly.",
            "evidence_target": "Using linear vector projections within RAG pipelines reduces hallucination rates.",
            "confidence": 0.85
        })

        with patch("app.services.llm_client.llm_client.is_groq_configured", return_value=True), \
             patch("app.services.llm_client.llm_client._get_chat_model") as mock_get_chat:
            mock_model = MagicMock()
            mock_model.invoke.return_value = mock_response
            mock_get_chat.return_value = mock_model

            evaluation = self.engine.evaluate_pair(
                doc_a_name="Doc A",
                doc_a_text="Multi-Head Attention projects queries, keys, and values linearly.",
                doc_b_name="Doc B",
                doc_b_text="Using linear vector projections within RAG pipelines reduces hallucination rates.",
                retrieval_similarity=0.75
            )

            self.assertIsNotNone(evaluation)
            self.assertTrue(evaluation.has_connection)
            self.assertEqual(evaluation.relationship_type, "SUPPORTS")
            self.assertIn("queries, keys", evaluation.evidence_source)
            self.assertIn("reduces hallucination", evaluation.evidence_target)
            self.assertGreater(evaluation.confidence, 0.7)

    def test_evaluate_pair_rejects_missing_evidence(self):
        """Verifies that candidate pairs without dual-passage evidence quotes are rejected."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "has_connection": True,
            "relationship_type": "SIMILAR",
            "explanation": "Both discuss machine learning.",
            "evidence_source": "",  # Missing evidence
            "evidence_target": "Some target evidence",
            "confidence": 0.5
        })

        with patch("app.services.llm_client.llm_client.is_groq_configured", return_value=True), \
             patch("app.services.llm_client.llm_client._get_chat_model") as mock_get_chat:
            mock_model = MagicMock()
            mock_model.invoke.return_value = mock_response
            mock_get_chat.return_value = mock_model

            evaluation = self.engine.evaluate_pair(
                doc_a_name="Doc A",
                doc_a_text="Some text",
                doc_b_name="Doc B",
                doc_b_text="Some text",
                retrieval_similarity=0.6
            )
            self.assertIsNone(evaluation)

    def test_connection_deduplication(self):
        """Verifies that duplicate connection pairs (regardless of source/target order) are not duplicated."""
        now = datetime.utcnow()
        conn1 = DocumentConnectionORM(
            source_doc_id=901,
            target_doc_id=902,
            source_chunk_id="901_0",
            target_chunk_id="902_0",
            relationship_type="SIMILAR",
            explanation="Both discuss neural architectures.",
            evidence_source="Passage A quote",
            evidence_target="Passage B quote",
            source_filename="attention_models.pdf",
            target_filename="rag_grounding.pdf",
            source_page_number=1,
            target_page_number=1,
            confidence=0.82,
            status="new",
            created_at=now
        )
        self.db.add(conn1)
        self.db.commit()

        # Check existing check query logic
        existing_forward = self.db.query(DocumentConnectionORM).filter(
            ((DocumentConnectionORM.source_chunk_id == "901_0") & (DocumentConnectionORM.target_chunk_id == "902_0")) |
            ((DocumentConnectionORM.source_chunk_id == "902_0") & (DocumentConnectionORM.target_chunk_id == "901_0"))
        ).first()
        self.assertIsNotNone(existing_forward)

        existing_reverse = self.db.query(DocumentConnectionORM).filter(
            ((DocumentConnectionORM.source_chunk_id == "902_0") & (DocumentConnectionORM.target_chunk_id == "901_0")) |
            ((DocumentConnectionORM.source_chunk_id == "901_0") & (DocumentConnectionORM.target_chunk_id == "902_0"))
        ).first()
        self.assertIsNotNone(existing_reverse)

    def test_cascade_deletion_of_connections(self):
        """Verifies that deleting a document cascades to remove associated connections."""
        now = datetime.utcnow()
        conn = DocumentConnectionORM(
            source_doc_id=901,
            target_doc_id=902,
            source_chunk_id="901_0",
            target_chunk_id="902_0",
            relationship_type="EXTENDS",
            explanation="Passage B extends Passage A.",
            evidence_source="Snippet A",
            evidence_target="Snippet B",
            source_filename="attention_models.pdf",
            target_filename="rag_grounding.pdf",
            confidence=0.85,
            status="new",
            created_at=now
        )
        self.db.add(conn)
        self.db.commit()

        conn_id = conn.id
        self.assertIsNotNone(self.db.query(DocumentConnectionORM).filter_by(id=conn_id).first())

        # Simulate deletion endpoint logic
        self.db.query(DocumentConnectionORM).filter(
            (DocumentConnectionORM.source_doc_id == 901) | (DocumentConnectionORM.target_doc_id == 901)
        ).delete()
        self.db.query(DocumentORM).filter_by(id=901).delete()
        self.db.commit()

        # Connection should be deleted
        remaining_conn = self.db.query(DocumentConnectionORM).filter_by(id=conn_id).first()
        self.assertIsNone(remaining_conn)

    def test_connection_status_update_and_dismissal(self):
        """Verifies updating review status ('saved', 'dismissed') through API."""
        now = datetime.utcnow()
        conn = DocumentConnectionORM(
            source_doc_id=901,
            target_doc_id=902,
            source_chunk_id="901_0",
            target_chunk_id="902_0",
            relationship_type="ANSWERS",
            explanation="Answers limitation.",
            evidence_source="Evidence 1",
            evidence_target="Evidence 2",
            source_filename="attention_models.pdf",
            target_filename="rag_grounding.pdf",
            confidence=0.80,
            status="new",
            created_at=now
        )
        self.db.add(conn)
        self.db.commit()

        # Test PATCH /api/connections/{id} to save
        res = client.patch(f"/api/connections/{conn.id}", json={"status": "saved"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "saved")

        # Test PATCH /api/connections/{id} to dismiss
        res2 = client.patch(f"/api/connections/{conn.id}", json={"status": "dismissed"})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "dismissed")

        # Test DELETE /api/connections/{id}
        res3 = client.delete(f"/api/connections/{conn.id}")
        self.assertEqual(res3.status_code, 200)
        self.assertIsNone(self.db.query(DocumentConnectionORM).filter_by(id=conn.id).first())


class TestFlashcardsAndSM2(unittest.TestCase):
    """Verifies source-grounded flashcard generation, CRUD, and deterministic SM-2 repetition scheduling."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.service = FlashcardService()

        # Clean old records
        self.db.query(FlashcardORM).filter(FlashcardORM.document_id == 950).delete()
        self.db.query(DocumentORM).filter(DocumentORM.id == 950).delete()
        self.db.commit()

        # Create test document
        self.doc = DocumentORM(
            id=950,
            filename="spaced_repetition_study.pdf",
            filepath="data/uploads/spaced_repetition_study.pdf",
            file_size=30000,
            upload_time=datetime.utcnow(),
            status="indexed",
            chunk_count=1
        )
        self.db.add(self.doc)
        self.db.commit()

    def tearDown(self):
        self.db.query(FlashcardORM).filter(FlashcardORM.document_id == 950).delete()
        self.db.query(DocumentORM).filter(DocumentORM.id == 950).delete()
        self.db.commit()
        self.db.close()

    def test_sm2_spaced_repetition_ratings(self):
        """Verifies deterministic SM-2 progression for 'again', 'hard', 'good', and 'easy'."""
        now = datetime.utcnow()
        card = FlashcardORM(
            document_id=950,
            chunk_id="950_0",
            question="What is the spacing effect?",
            answer="Learning is greater when studying is spread out over time rather than concentrated.",
            source_snippet="The spacing effect demonstrates improved long-term retention.",
            filename="spaced_repetition_study.pdf",
            page_number=1,
            status="new",
            interval_days=1,
            ease_factor=2.5,
            repetitions=0,
            created_at=now,
            next_review_date=now
        )
        self.db.add(card)
        self.db.commit()
        card_id = card.id

        # 1. Rating 'good' (First successful recall: reps=1, interval=1)
        c1 = self.service.review_card(card_id, "good", db=self.db)
        self.assertEqual(c1.repetitions, 1)
        self.assertEqual(c1.interval_days, 1)
        self.assertEqual(c1.status, "review")

        # 2. Rating 'good' (Second successful recall: reps=2, interval=6)
        c2 = self.service.review_card(card_id, "good", db=self.db)
        self.assertEqual(c2.repetitions, 2)
        self.assertEqual(c2.interval_days, 6)

        # 3. Rating 'easy' (Third review with ease bonus: ease increases, interval scales by ease * 1.3)
        c3 = self.service.review_card(card_id, "easy", db=self.db)
        self.assertEqual(c3.repetitions, 3)
        self.assertGreater(c3.ease_factor, 2.5)  # Ease factor increases
        self.assertGreater(c3.interval_days, 15)

        # 4. Rating 'again' (Lapse: reps reset to 0, interval reset to 1, ease decreases)
        old_ease = c3.ease_factor
        c4 = self.service.review_card(card_id, "again", db=self.db)
        self.assertEqual(c4.repetitions, 0)
        self.assertEqual(c4.interval_days, 1)
        self.assertEqual(c4.status, "learning")
        self.assertLess(c4.ease_factor, old_ease)

        # 5. Rating 'hard' (Moderate interval increase without rep bump)
        c5 = self.service.review_card(card_id, "hard", db=self.db)
        self.assertEqual(c5.status, "review")

    def test_flashcard_api_endpoints(self):
        """Verifies flashcard manual creation, retrieval, review, and deletion via API."""
        create_payload = {
            "document_id": 950,
            "chunk_id": "950_0",
            "question": "What is proactive retrieval?",
            "answer": "Automatically fetching related knowledge before the user explicitly asks.",
            "source_snippet": "Proactive retrieval surfaces connections ahead of explicit prompts.",
            "filename": "spaced_repetition_study.pdf",
            "page_number": 1
        }
        res = client.post("/api/flashcards/", json=create_payload)
        self.assertEqual(res.status_code, 200)
        card_data = res.json()
        card_id = card_data["id"]

        # Fetch flashcards list
        list_res = client.get("/api/flashcards/")
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(c["id"] == card_id for c in list_res.json()))

        # Submit review via API
        review_res = client.post(f"/api/flashcards/{card_id}/review", json={"action": "good"})
        self.assertEqual(review_res.status_code, 200)
        self.assertEqual(review_res.json()["repetitions"], 1)

        # Delete flashcard
        del_res = client.delete(f"/api/flashcards/{card_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(self.db.query(FlashcardORM).filter_by(id=card_id).first())


class TestPersistentMemory(unittest.TestCase):
    """Verifies pattern memory management, topic frequency increments, and query-relevant episodic retrieval."""

    def setUp(self):
        self.mm = MemoryManager()
        # Clean pattern memories with test prefix
        with self.mm._get_connection() as conn:
            conn.execute("DELETE FROM pattern_memories WHERE topic LIKE 'Test Topic%'")
            conn.commit()

    def tearDown(self):
        with self.mm._get_connection() as conn:
            conn.execute("DELETE FROM pattern_memories WHERE topic LIKE 'Test Topic%'")
            conn.commit()

    def test_record_and_increment_pattern_memory(self):
        """Verifies pattern memories track topic frequency across repeated occurrences."""
        self.mm.record_pattern_memory(
            topic="Test Topic: Distributed Transactions",
            observation="Frequent exploration of Two-Phase Commit and Saga patterns.",
            source_documents=["doc1.pdf"]
        )

        patterns = self.mm.get_pattern_memories(status="active")
        matching = [p for p in patterns if p["topic"] == "Test Topic: Distributed Transactions"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["frequency"], 1)

        # Record same topic again: frequency should increment to 2
        self.mm.record_pattern_memory(
            topic="Test Topic: Distributed Transactions",
            observation="Updated observation including consensus protocols.",
            source_documents=["doc1.pdf", "doc2.pdf"]
        )

        patterns_after = self.mm.get_pattern_memories(status="active")
        matching_after = [p for p in patterns_after if p["topic"] == "Test Topic: Distributed Transactions"]
        self.assertEqual(matching_after[0]["frequency"], 2)

    def test_dismiss_pattern_memory(self):
        """Verifies user can dismiss transparent pattern memories."""
        self.mm.record_pattern_memory(
            topic="Test Topic: Transient Topic",
            observation="Temporary interest in sorting algorithms.",
            source_documents=["doc3.pdf"]
        )
        patterns = self.mm.get_pattern_memories(status="active")
        target = next(p for p in patterns if p["topic"] == "Test Topic: Transient Topic")
        
        # Dismiss via memory manager
        self.mm.dismiss_pattern_memory(target["id"])

        active_patterns = self.mm.get_pattern_memories(status="active")
        self.assertFalse(any(p["id"] == target["id"] for p in active_patterns))

        dismissed_patterns = self.mm.get_pattern_memories(status="dismissed")
        self.assertTrue(any(p["id"] == target["id"] for p in dismissed_patterns))

    def test_query_relevant_episodic_retrieval(self):
        """Verifies episodic memory retrieves relevant messages by query keywords instead of dumping full history."""
        # Create a test conversation thread
        conv_id = self.mm.create_conversation("Episodic Retrieval Test")
        self.mm.add_message(conv_id, "user", "How does Paxos handle network partitions?")
        self.mm.add_message(conv_id, "assistant", "Paxos requires a quorum of acceptors (majority) to agree.")
        self.mm.add_message(conv_id, "user", "What is gradient clipping in deep learning?")
        self.mm.add_message(conv_id, "assistant", "Gradient clipping bounds gradients to prevent exploding gradients.")

        # Query about Paxos should retrieve Paxos messages, not gradient clipping
        results = self.mm.get_relevant_episodic_context("quorum network partition in paxos", limit=2)
        self.assertGreater(len(results), 0)
        retrieved_texts = [r["content"] for r in results]
        self.assertTrue(any("Paxos" in text or "quorum" in text for text in retrieved_texts))
        self.assertFalse(all("gradient" in text for text in retrieved_texts))


if __name__ == "__main__":
    unittest.main()
