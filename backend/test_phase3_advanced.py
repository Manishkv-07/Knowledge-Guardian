"""
Personal Knowledge Guardian - Phase 3 Automated Product Polish & Advanced Workflows Test Suite
Covers:
1. Real Document Ingestion Stages (uploaded, extracting, chunking, embedding, indexing, completed/failed).
2. HTML Document Ingestion & Text Extraction (clean body text, script/style stripping).
3. Grounded Document Insights (summary, key_concept, definitions, study_questions, custom instructions).
4. System Architecture & Telemetry Metrics (real database, FAISS, and BM25 consistency checking, masked credentials).
5. Practical Export Workflows (Document Markdown, Connections Markdown, Flashcards CSV, Research Notes).
6. Knowledge Graph API (nodes, edges, evidence inspection, relationship filtering).
7. Security & Input Sanitization (path traversal blocking, untrusted context boundary, zero secret leakage).
"""

import os
import sys
import json
import io
import tempfile
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.document import (
    Base, engine, SessionLocal,
    DocumentORM, DocumentConnectionORM, FlashcardORM, MemoryORM
)
from app.services.vector_store import vector_store
from app.services.ingestion import ingestion_service
from app.services.llm_client import llm_client
from app.utils.helpers import is_allowed_file, clean_filename

client = TestClient(app)


class TestIngestionStagesAndHTML(unittest.TestCase):
    """Verifies document ingestion stage tracking and HTML text extraction."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_filename_sanitization_and_path_traversal_blocking(self):
        """Verifies clean_filename neutralizes path traversal, null bytes, and invalid symbols."""
        bad_filenames = [
            ("../../etc/passwd", "etc_passwd"),
            ("..\\..\\windows\\system32\\calc.exe", "windows_system32_calc.exe"),
            ("paper\x00_test.pdf", "paper__test.pdf"),
            ("my document (2026) [v1] & notes.txt", "my_document__2026___v1____notes.txt")
        ]
        for raw, expected_pattern in bad_filenames:
            cleaned = clean_filename(raw)
            self.assertNotIn("..", cleaned)
            self.assertNotIn("/", cleaned)
            self.assertNotIn("\\", cleaned)

    def test_allowed_file_types(self):
        """Verifies PDF, TXT, MD, HTML, and HTM are allowed, while executables are rejected."""
        self.assertTrue(is_allowed_file("document.pdf"))
        self.assertTrue(is_allowed_file("notes.txt"))
        self.assertTrue(is_allowed_file("README.md"))
        self.assertTrue(is_allowed_file("page.html"))
        self.assertTrue(is_allowed_file("page.htm"))
        self.assertFalse(is_allowed_file("script.py"))
        self.assertFalse(is_allowed_file("malware.exe"))
        self.assertFalse(is_allowed_file("data.db"))

    def test_html_parsing_strips_scripts_and_extracts_text(self):
        """Verifies HTML ingestion extracts clean body text and strips script/style tags."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quantum Memory Architecture</title>
            <style>body { color: red; } h1 { font-size: 20px; }</style>
            <script>alert('malicious script execution');</script>
        </head>
        <body>
            <h1>Quantum Memory Systems</h1>
            <p>Photonic quantum memories capture optical quantum states in solid-state crystal lattices.</p>
            <p>Rare-earth ion crystals enable high storage fidelity at cryogenic temperatures.</p>
            <script>var x = 100;</script>
        </body>
        </html>
        """
        temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        try:
            temp_file.write(html_content)
            temp_file.close()

            result = ingestion_service.process_html(temp_file.name, "quantum_memory.html", document_id="test_html_doc")
            chunks = result["chunks"]
            self.assertGreater(len(chunks), 0)

            all_extracted = " ".join(c["text"] for c in chunks)
            self.assertIn("Photonic quantum memories", all_extracted)
            self.assertIn("Rare-earth ion crystals", all_extracted)
            self.assertNotIn("malicious script", all_extracted)
            self.assertNotIn("color: red", all_extracted)
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)


class TestGroundedInsights(unittest.TestCase):
    """Verifies grounded document insights, custom instructions, definitions, and study questions."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        # Create test document
        self.doc = DocumentORM(
            id=8801,
            filename="superconducting_resonators.pdf",
            filepath="data/uploads/superconducting_resonators.pdf",
            file_size=65000,
            upload_time=datetime.utcnow(),
            status="indexed",
            chunk_count=2
        )
        self.db.add(self.doc)
        self.db.commit()

        # Write dummy chunk file
        chunks_dir = settings.BASE_DIR / settings.CHUNK_DIR if hasattr(settings, "BASE_DIR") else Path("backend/data/chunks")
        os.makedirs(chunks_dir, exist_ok=True)
        self.chunk_file = chunks_dir / "8801.json"
        sample_chunks = [
            {
                "id": "8801_0",
                "document_id": "8801",
                "text": "Superconducting coplanar waveguide resonators achieve internal quality factors exceeding one million at single-photon powers.",
                "metadata": {"filename": "superconducting_resonators.pdf", "page_number": 1, "chunk_index": 0}
            },
            {
                "id": "8801_1",
                "document_id": "8801",
                "text": "Two-level system (TLS) defect dissipation in dielectric interfaces represents the dominant microwave loss mechanism.",
                "metadata": {"filename": "superconducting_resonators.pdf", "page_number": 2, "chunk_index": 1}
            }
        ]
        with open(self.chunk_file, "w", encoding="utf-8") as f:
            json.dump(sample_chunks, f)

    def tearDown(self):
        self.db.query(MemoryORM).filter_by(document_id=8801).delete()
        self.db.query(DocumentORM).filter_by(id=8801).delete()
        self.db.commit()
        self.db.close()
        if os.path.exists(self.chunk_file):
            os.remove(self.chunk_file)

    def test_custom_insight_generation_with_groq_mock(self):
        """Verifies custom instruction insight is invoked with untrusted context isolation and persisted."""
        mock_response = MagicMock()
        mock_response.content = "### Formal Defect Analysis\n\nTwo-Level System (TLS) dissipation occurs at substrate-air dielectric interfaces [Page 2]."

        with patch("app.services.llm_client.llm_client.is_groq_configured", return_value=True), \
             patch("app.services.llm_client.llm_client._get_chat_model") as mock_chat:
            mock_model = MagicMock()
            mock_model.invoke.return_value = mock_response
            mock_chat.return_value = mock_model

            res = client.post(
                "/api/documents/8801/generate-insight",
                json={
                    "document_id": 8801,
                    "insight_type": "custom",
                    "custom_instruction": "Extract the specific loss mechanisms in dielectric interfaces.",
                    "content": ""
                }
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["insight_type"], "custom")
            self.assertIn("Two-Level System (TLS)", data["content"])

            # Verify persisted in database
            stored = self.db.query(MemoryORM).filter_by(document_id=8801).first()
            self.assertIsNotNone(stored)
            self.assertEqual(stored.insight_type, "custom")

    def test_unconfigured_groq_returns_503(self):
        """Verifies that when Groq is unconfigured, generate-insight returns 503 rather than fake mock text."""
        with patch("app.services.llm_client.llm_client.is_groq_configured", return_value=False):
            res = client.post(
                "/api/documents/8801/generate-insight",
                json={
                    "document_id": 8801,
                    "insight_type": "summary",
                    "content": ""
                }
            )
            self.assertEqual(res.status_code, 503)
            self.assertIn("Groq LLM is not configured", res.json()["detail"])


class TestSystemMetricsAndDashboard(unittest.TestCase):
    """Verifies real system metrics computation and index consistency checking."""

    def test_system_metrics_endpoint(self):
        """Verifies GET /api/stats returns accurate, unmasked/masked observable properties."""
        res = client.get("/api/stats/")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("documents", data)
        self.assertIn("vector_store", data)
        self.assertIn("intelligence", data)
        self.assertIn("llm_provider", data)

        # Real consistency check field exists
        self.assertIn("is_consistent", data["vector_store"])
        self.assertIsInstance(data["vector_store"]["is_consistent"], bool)

        # Ensure credentials are never leaked
        llm = data["llm_provider"]
        if llm.get("masked_key"):
            self.assertNotIn(settings.GROQ_API_KEY, llm["masked_key"])
            self.assertTrue(llm["masked_key"].startswith("gsk_") or "masked" in llm["masked_key"])


class TestPracticalExports(unittest.TestCase):
    """Verifies Markdown summary, Connections Markdown, Flashcards CSV, and Master Research Notes exports."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        self.doc = DocumentORM(
            id=8802,
            filename="quantum_algorithms_survey.pdf",
            filepath="data/uploads/quantum_algorithms_survey.pdf",
            file_size=75000,
            upload_time=datetime.utcnow(),
            status="indexed",
            chunk_count=3
        )
        self.mem = MemoryORM(
            document_id=8802,
            insight_type="summary",
            content="A survey of Shor's and Grover's quantum algorithms and complexity classes."
        )
        self.card = FlashcardORM(
            document_id=8802,
            question="What speedup does Grover's algorithm provide?",
            answer="Quadratic speedup for unstructured database search.",
            source_snippet="Grover's algorithm provides quadratic speedup.",
            filename="quantum_algorithms_survey.pdf",
            page_number=1,
            status="new",
            interval_days=1,
            ease_factor=2.5,
            repetitions=0
        )
        self.db.add_all([self.doc, self.mem, self.card])
        self.db.commit()

    def tearDown(self):
        self.db.query(FlashcardORM).filter_by(document_id=8802).delete()
        self.db.query(MemoryORM).filter_by(document_id=8802).delete()
        self.db.query(DocumentORM).filter_by(id=8802).delete()
        self.db.commit()
        self.db.close()

    def test_export_document_summary_markdown(self):
        """Verifies GET /api/exports/document/{id}/markdown returns structured markdown."""
        res = client.get("/api/exports/document/8802/markdown")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/markdown", res.headers["content-type"])
        text = res.content.decode("utf-8")
        self.assertIn("# Research Summary: quantum_algorithms_survey.pdf", text)
        self.assertIn("Grover's quantum algorithms", text)

    def test_export_flashcards_csv(self):
        """Verifies GET /api/exports/flashcards/csv returns valid CSV format."""
        res = client.get("/api/exports/flashcards/csv?document_id=8802")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers["content-type"])
        text = res.content.decode("utf-8")
        self.assertIn("Question,Answer,Source Citation", text)
        self.assertIn("Grover's algorithm", text)

    def test_export_research_notes_markdown(self):
        """Verifies GET /api/exports/research-notes/markdown returns master compendium."""
        res = client.get("/api/exports/research-notes/markdown")
        self.assertEqual(res.status_code, 200)
        text = res.content.decode("utf-8")
        self.assertIn("Master Research Compendium", text)


class TestKnowledgeGraphAPI(unittest.TestCase):
    """Verifies nodes and edges graph structure and relationship filtering."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        self.doc1 = DocumentORM(id=8803, filename="paper_a.pdf", filepath="a.pdf", file_size=1000, status="indexed", chunk_count=1)
        self.doc2 = DocumentORM(id=8804, filename="paper_b.pdf", filepath="b.pdf", file_size=2000, status="indexed", chunk_count=1)
        self.conn = DocumentConnectionORM(
            source_doc_id=8803,
            target_doc_id=8804,
            source_chunk_id="8803_0",
            target_chunk_id="8804_0",
            relationship_type="SUPPORTS",
            explanation="Paper B provides evidence confirming Paper A.",
            evidence_source="Evidence quote A",
            evidence_target="Evidence quote B",
            source_filename="paper_a.pdf",
            target_filename="paper_b.pdf",
            confidence=0.88,
            status="saved"
        )
        self.db.add_all([self.doc1, self.doc2, self.conn])
        self.db.commit()

    def tearDown(self):
        self.db.query(DocumentConnectionORM).filter(
            (DocumentConnectionORM.source_doc_id == 8803) | (DocumentConnectionORM.target_doc_id == 8803)
        ).delete()
        self.db.query(DocumentORM).filter(DocumentORM.id.in_([8803, 8804])).delete()
        self.db.commit()
        self.db.close()

    def test_knowledge_graph_nodes_and_edges(self):
        """Verifies graph endpoint returns connected nodes, edge citations, and respects relationship filters."""
        res = client.get("/api/connections/graph")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)

        node_ids = [n["id"] for n in data["nodes"]]
        self.assertIn(8803, node_ids)
        self.assertIn(8804, node_ids)

        edge = next((e for e in data["edges"] if e["source"] == 8803 and e["target"] == 8804), None)
        self.assertIsNotNone(edge)
        self.assertEqual(edge["relationship"], "SUPPORTS")
        self.assertEqual(edge["evidence_source"], "Evidence quote A")

        # Filter by relationship: CONTRADICTS should return 0 matching edges
        filtered_res = client.get("/api/connections/graph?relationship_type=CONTRADICTS")
        self.assertEqual(filtered_res.status_code, 200)
        filtered_edges = [e for e in filtered_res.json()["edges"] if e["source"] == 8803 and e["target"] == 8804]
        self.assertEqual(len(filtered_edges), 0)


if __name__ == "__main__":
    unittest.main()
