import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm_client import llm_client

def test_connection():
    print("=" * 60)
    print(" TESTING CONNECTION TO GOOGLE COLAB OLLAMA ".center(60, "="))
    print("=" * 60)
    
    print(f"Configured Endpoint URL : {llm_client.base_url}")
    print(f"Configured Model Name   : {llm_client.model}")
    
    if not llm_client.base_url:
        print("[ERROR] base_url is empty in settings!")
        return

    # Sample chunks for RAG test
    chunks = [
        {
            "document_id": "1",
            "filename": "test_guide.pdf",
            "text": "The attention mechanism in transformers allows the model to focus on different parts of the input sequence when generating output. Self-attention relates different positions of a single sequence to compute a representation of the sequence."
        }
    ]
    
    query = "What does the attention mechanism do?"
    
    print(f"\n1. Testing non-streaming response for query: '{query}'...")
    try:
        res = llm_client.generate_answer(query, chunks)
        print(f"Response Status: SUCCESS")
        print(f"Answer:\n{res.get('answer')}")
    except Exception as e:
        print(f"[ERROR] Non-streaming request failed: {e}")

if __name__ == "__main__":
    test_connection()
