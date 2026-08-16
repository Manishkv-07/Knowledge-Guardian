import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm_client import llm_client

async def test_stream():
    print("=" * 60)
    print(" TESTING STREAMING FROM LLMCLIENT ".center(60, "="))
    print("=" * 60)
    
    chunks = [
        {
            "document_id": "1",
            "filename": "test_guide.pdf",
            "text": "The attention mechanism in transformers allows the model to focus on different parts of the input sequence when generating output."
        }
    ]
    
    query = "What does the attention mechanism do?"
    
    print(f"Query: '{query}'")
    print(f"Endpoint: {llm_client.base_url}")
    print("-" * 50)
    
    try:
        async for token in llm_client.generate_answer_stream(query, chunks):
            print(token, end="", flush=True)
        print("\n" + "-" * 50)
        print("✓ Stream completed successfully.")
    except Exception as e:
        print(f"\n❌ Stream failed with error: {e}")
        
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_stream())
