import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.llm_client import LLMClient
from app.config import settings
from fastapi.testclient import TestClient
from app.main import app

class TestGroqIntegration(unittest.TestCase):
    def setUp(self):
        self.llm_client = LLMClient()
        self.sample_chunks = [
            {
                "chunk_id": "chunk_doc1_0",
                "document_id": "doc1",
                "filename": "neural_networks.pdf",
                "page_number": 2,
                "text": "Backpropagation calculates the gradient of the loss function with respect to each weight.",
                "similarity": 0.94
            },
            {
                "chunk_id": "chunk_doc2_1",
                "document_id": "doc2",
                "filename": "transformers_guide.txt",
                "page_number": None,
                "text": "Multi-head attention allows the model to jointly attend to information at different positions.",
                "similarity": 0.91
            }
        ]

    def test_1_missing_or_placeholder_api_key_handling(self):
        """Test that missing or placeholder API key is safely detected and clear instructions are returned."""
        with patch.dict(os.environ, {"GROQ_API_KEY": "replace_with_my_actual_key"}):
            client = LLMClient()
            self.assertFalse(client.is_groq_configured())
            
            res = client.generate_answer("What is backpropagation?", self.sample_chunks)
            self.assertIn("GROQ_API_KEY", res["answer"])
            self.assertIn("not configured", res["answer"])
            # Sources must still be preserved for the frontend
            self.assertEqual(len(res["sources"]), 2)
            self.assertEqual(res["sources"][0]["label"], "[S1]")
            self.assertEqual(res["sources"][0]["filename"], "neural_networks.pdf")
            self.assertEqual(res["sources"][0]["page_number"], 2)

        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            client = LLMClient()
            self.assertFalse(client.is_groq_configured())
            res = client.generate_answer("What is attention?", self.sample_chunks)
            self.assertIn("GROQ_API_KEY", res["answer"])

    def test_2_empty_document_retrieval(self):
        """Test that querying with no retrieved chunks returns a helpful message without calling LLM."""
        res = self.llm_client.generate_answer("Unanswerable question", [])
        self.assertIn("couldn't find any relevant information", res["answer"].lower())
        self.assertEqual(res["sources"], [])

        # Empty query
        res_empty = self.llm_client.generate_answer("", self.sample_chunks)
        self.assertIn("cannot be empty", res_empty["answer"].lower())

    def test_3_prompt_construction_and_source_labels(self):
        """Test that system prompt enforces strict context grounding and builds [S1], [S2] source labels."""
        messages = self.llm_client._build_prompt_messages("How does attention work?", self.sample_chunks)
        self.assertEqual(len(messages), 2)
        
        system_content = messages[0].content
        self.assertIn("ONLY use information directly contained", system_content)
        self.assertIn("[S1]", system_content)
        self.assertIn("The retrieved documents do not contain enough information", system_content)
        self.assertIn("Never invent", system_content)

        user_content = messages[1].content
        self.assertIn("[S1] (Document: neural_networks.pdf, Page: 2):", user_content)
        self.assertIn("Backpropagation calculates the gradient", user_content)
        self.assertIn("[S2] (Document: transformers_guide.txt):", user_content)
        self.assertIn("Multi-head attention allows the model", user_content)
        self.assertIn("Question:\nHow does attention work?", user_content)

    def test_4_source_metadata_preservation(self):
        """Test that structured source records preserve source_id, label, filename, page_number, similarity."""
        sources = self.llm_client._format_sources(self.sample_chunks)
        self.assertEqual(len(sources), 2)
        
        # Source 1
        s1 = sources[0]
        self.assertEqual(s1["source_id"], "S1")
        self.assertEqual(s1["label"], "[S1]")
        self.assertEqual(s1["filename"], "neural_networks.pdf")
        self.assertEqual(s1["page_number"], 2)
        self.assertEqual(s1["document_id"], "doc1")
        self.assertEqual(s1["chunk_id"], "chunk_doc1_0")
        self.assertEqual(s1["similarity"], 0.94)

        # Source 2
        s2 = sources[1]
        self.assertEqual(s2["source_id"], "S2")
        self.assertEqual(s2["label"], "[S2]")
        self.assertEqual(s2["filename"], "transformers_guide.txt")
        self.assertIsNone(s2["page_number"])
        self.assertEqual(s2["similarity"], 0.91)

    @patch("app.services.llm_client.ChatGroq")
    def test_5_provider_failure_and_rate_limit_handling(self, mock_chat_groq):
        """Test error handling when Groq encounters RateLimitError, AuthenticationError, or Timeout."""
        import groq

        # 5a. Rate Limit Error (HTTP 429)
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_instance.invoke.side_effect = groq.RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit reached"}}
        )
        mock_chat_groq.return_value = mock_instance

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_mock_valid_key"}):
            client = LLMClient()
            res = client.generate_answer("Explain attention", self.sample_chunks)
            self.assertIn("429", res["answer"])
            self.assertIn("rate limit", res["answer"].lower())

        # 5b. Authentication Error (HTTP 401)
        mock_response.status_code = 401
        mock_instance.invoke.side_effect = groq.AuthenticationError(
            message="Invalid API Key",
            response=mock_response,
            body={"error": {"message": "Invalid key"}}
        )
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_mock_valid_key"}):
            client = LLMClient()
            res = client.generate_answer("Explain attention", self.sample_chunks)
            self.assertIn("Invalid Groq API key", res["answer"])

        # 5c. Timeout Error
        mock_instance.invoke.side_effect = groq.APITimeoutError(request=MagicMock())
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_mock_valid_key"}):
            client = LLMClient()
            res = client.generate_answer("Explain attention", self.sample_chunks)
            self.assertIn("timed out", res["answer"].lower())

    @patch("app.services.llm_client.ChatGroq")
    def test_6_successful_groq_answer_generation(self, mock_chat_groq):
        """Test that valid ChatGroq response returns grounded answer and source metadata."""
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "Multi-head attention projects queries, keys, and values [S2]."
        mock_instance.invoke.return_value = mock_result
        mock_chat_groq.return_value = mock_instance

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_mock_valid_key", "GROQ_MODEL": "openai/gpt-oss-120b"}):
            client = LLMClient()
            res = client.generate_answer("How does multi-head attention work?", self.sample_chunks)
            self.assertEqual(res["answer"], "Multi-head attention projects queries, keys, and values [S2].")
            self.assertEqual(res["model"], "openai/gpt-oss-120b")
            self.assertEqual(len(res["sources"]), 2)
            self.assertEqual(res["sources"][0]["label"], "[S1]")
            self.assertEqual(res["sources"][1]["label"], "[S2]")

    def test_7_existing_endpoint_compatibility(self):
        """Test FastAPI endpoint /api/query compatibility with test client."""
        test_client = TestClient(app)
        
        # Test conversation creation
        conv_resp = test_client.post("/api/chat/conversations", json={"title": "Groq Integration Test"})
        self.assertEqual(conv_resp.status_code, 200)
        conv_id = conv_resp.json()["id"]

        # Test query endpoint
        query_resp = test_client.post("/api/query", json={
            "query": "What is the attention mechanism?",
            "conversation_id": conv_id
        })
        self.assertEqual(query_resp.status_code, 200)
        data = query_resp.json()
        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertEqual(data["conversation_id"], conv_id)

        # Cleanup conversation
        del_resp = test_client.delete(f"/api/chat/conversations/{conv_id}")
        self.assertEqual(del_resp.status_code, 200)

if __name__ == "__main__":
    unittest.main()
