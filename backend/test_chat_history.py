import sys
import os
from pathlib import Path

# Add backend directory to PYTHONPATH so we can import app modules
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from app.services.memory_manager import memory_manager

def run_tests():
    print("=== Running Chat History (Episodic Memory) Tests ===")
    
    # 1. Create a conversation
    print("\n1. Testing Create Conversation...")
    conv_id1 = memory_manager.create_conversation("Transformer Basics")
    print(f"Created Conversation 1: {conv_id1}")
    
    conv_id2 = memory_manager.create_conversation("RAG Architectures")
    print(f"Created Conversation 2: {conv_id2}")
    
    # 2. Add messages
    print("\n2. Testing Add Messages...")
    # Add messages to conversation 1
    m1 = memory_manager.add_message(
        conversation_id=conv_id1,
        role="user",
        content="What is attention mechanism?"
    )
    print(f"Added user message: {m1}")
    
    m2 = memory_manager.add_message(
        conversation_id=conv_id1,
        role="assistant",
        content="Rather than performing a single attention function, Multi-Head Attention projects the queries, keys, and values h times...",
        sources=[{
            "document_id": "doc_attention",
            "filename": "transformer_attention_mechanisms.txt",
            "chunk_id": "chunk_attention_0",
            "text": "Rather than performing a single attention function, Multi-Head Attention projects...",
            "similarity": 0.923
        }]
    )
    print(f"Added assistant message: {m2}")
    
    # Add messages to conversation 2
    m3 = memory_manager.add_message(
        conversation_id=conv_id2,
        role="user",
        content="How does RAG work?"
    )
    print(f"Added user message: {m3}")
    
    m4 = memory_manager.add_message(
        conversation_id=conv_id2,
        role="assistant",
        content="Retrieval-Augmented Generation (RAG) combines an LLM with an external search engine/vector index. The system retrieves matching paragraphs...",
        sources=[{
            "document_id": "doc_rag",
            "filename": "combating_hallucinations_rag.txt",
            "chunk_id": "chunk_rag_0",
            "text": "By coupling an LLM with a vector search database (like FAISS), we create a Retrieval-Augmented Generation (RAG) pipeline...",
            "similarity": 0.887
        }]
    )
    print(f"Added assistant message: {m4}")
    
    # 3. Retrieve conversation history
    print("\n3. Testing Get Conversations list...")
    conversations = memory_manager.get_conversations(limit=5)
    for c in conversations:
        print(f"- Conv: {c['title']} | Last Msg: {c['last_message']} | Updated: {c['updated_at']}")
        
    print(f"\n3b. Testing Get Messages for Conversation 1 ({conv_id1})...")
    messages = memory_manager.get_messages(conv_id1)
    for m in messages:
        print(f"  [{m['role'].upper()}]: {m['content']}")
        if m['sources']:
            print(f"  Sources: {m['sources']}")
            
    # 4. Rename Conversation
    print("\n4. Testing Rename Conversation...")
    original_title = ""
    for c in conversations:
        if c['id'] == conv_id2:
            original_title = c['title']
    print(f"Original title of Conv 2: {original_title}")
    
    memory_manager.rename_conversation(conv_id2, "Advanced RAG Pipeline")
    conversations_after = memory_manager.get_conversations(limit=5)
    for c in conversations_after:
        if c['id'] == conv_id2:
            print(f"New title of Conv 2: {c['title']}")
            
    # 5. Delete Conversation
    print("\n5. Testing Delete Conversation (Cascade messages)...")
    memory_manager.delete_conversation(conv_id1)
    print(f"Deleted conversation {conv_id1}")
    
    # Verify deletion
    conversations_final = memory_manager.get_conversations(limit=5)
    print("Remaining conversations in DB:")
    for c in conversations_final:
        print(f"- Conv: {c['title']} (ID: {c['id']})")
        
    print("\n=== Chat History Tests Completed Successfully ===")

if __name__ == "__main__":
    run_tests()
