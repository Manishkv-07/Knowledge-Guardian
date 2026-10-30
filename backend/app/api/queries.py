from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.models.chat import ChatQueryRequest, ChatQueryResponse
from app.services.memory_manager import memory_manager
from app.services.vector_store import vector_store
from app.services.llm_client import llm_client
from app.utils.helpers import logger

router = APIRouter(tags=["query"])

@router.post("/query", response_model=ChatQueryResponse)
async def query_knowledge_base_chat(request: ChatQueryRequest):
    """
    Handle a user query in a chat session:
    1. Validate empty query
    2. Create conversation if no conversation_id is provided or doesn't exist
    3. Save the user message to episodic memory
    4. Retrieve matching document chunks from vector store
    5. Generate response using LLM client (Colab Ollama / Modal)
    6. Save assistant message and sources to episodic memory
    7. Return conversation_id, answer, and sources
    """
    query = request.query
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    conversation_id = request.conversation_id

    # If no conversation_id, create a new conversation
    if not conversation_id:
        # Auto-title conversation using first 30 chars of query
        title = query[:30] + "..." if len(query) > 30 else query
        conversation_id = memory_manager.create_conversation(title=title)
    else:
        # Check if conversation exists
        try:
            # Check if conversation exists by querying it.
            # get_messages will raise ValueError if conversation doesn't exist.
            # We can use that or a simple check.
            memory_manager.get_messages(conversation_id)
        except ValueError:
            # If not found, create a new one to be resilient
            title = query[:30] + "..." if len(query) > 30 else query
            conversation_id = memory_manager.create_conversation(title=title)

    # 1. Save user message to database
    try:
        memory_manager.add_message(conversation_id=conversation_id, role="user", content=query)
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")
        raise HTTPException(status_code=500, detail=f"Database error saving user message: {str(e)}")

    # 2. Retrieve matching chunks from vector store
    chunks = []
    if vector_store.index is not None and vector_store.index.ntotal > 0:
        try:
            # Search top 5 chunks
            chunks = vector_store.search(query=query, k=5)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            # Keep chunks empty and continue to let LLM fallback respond
            chunks = []

    # 3. Generate answer via Groq LLM client (with safe fallback if Groq not configured)
    answer = ""
    sources = []
    
    # Try calling the Groq LLM client first
    if llm_client.is_groq_configured():
        try:
            llm_response = llm_client.generate_answer(query=query, chunks=chunks)
            answer = llm_response.get("answer", "")
            sources = llm_response.get("sources", [])
        except Exception as e:
            logger.error(f"Groq LLM generation failed: {e}")
            answer = f"⚠️ LLM service error: {str(e)}"
            sources = []
            
    # Fallback only when Groq is not configured or unexpected failure occurred
    if not answer.strip():
        logger.info("Groq is not configured. Returning retrieval-only fallback response...")
        if chunks:
            retrieved_texts = "\n\n".join([
                f"- [{c.get('filename', 'Source')}]: \"{c.get('text', '')[:250]}...\""
                for c in chunks[:3]
            ])
            answer = (
                "[Retrieval Fallback — LLM Not Configured]\n"
                "I retrieved relevant passages from your library, but Groq LLM is not configured. "
                "Add your GROQ_API_KEY to backend/.env to enable AI synthesis.\n\n"
                f"Retrieved Passages:\n{retrieved_texts}"
            )
            sources = chunks[:3]
        else:
            answer = (
                "I searched your knowledge base but couldn't find any relevant passages. "
                "Additionally, the Groq LLM is not configured. Please upload documents or add your "
                "GROQ_API_KEY to backend/.env."
            )
            sources = []

    # 4. Save assistant response to database
    try:
        memory_manager.add_message(conversation_id=conversation_id, role="assistant", content=answer, sources=sources)
    except Exception as e:
        logger.error(f"Failed to save assistant message: {e}")
        # Note: We still return the answer since it was successfully generated
        pass

    return ChatQueryResponse(
        conversation_id=conversation_id,
        answer=answer,
        sources=sources
    )
