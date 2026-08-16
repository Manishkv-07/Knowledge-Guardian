import os
import shutil
import httpx
import json
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

from app.config import settings
import math
from app.models.document import (
    get_db, DocumentORM, MemoryORM, DocumentResponse, MemoryResponse,
    QueryRequest, QueryResponse, PaginatedQueryResponse, QueryResultItem, RelatedChunk, MemoryCreate
)
from app.services.ingestion import ingestion_service
from app.services.vector_store import vector_store
from app.services.llm_client import llm_client
from app.services.memory_manager import memory_manager
from app.utils.helpers import logger, is_allowed_file, clean_filename

router = APIRouter(prefix="/documents", tags=["documents"])

def process_document_background(doc_id: int, filepath: str, filename: str, db_session_factory):
    """Background task to extract text, create chunks, embed, and index in FAISS vector store."""
    db = db_session_factory()
    db_doc = db.query(DocumentORM).filter(DocumentORM.id == doc_id).first()
    if not db_doc:
        db.close()
        return

    try:
        db_doc.status = "processing"
        db.commit()

        ext = filename.rsplit('.', 1)[1].lower()
        if ext == 'pdf':
            result = ingestion_service.process_pdf(filepath, filename, document_id=str(doc_id))
        else:
            result = ingestion_service.process_text(filepath, filename, document_id=str(doc_id))

        total_chunks = result["total_chunks"]

        # Add to vector store
        vector_store.add_document(str(doc_id))
        
        db_doc.status = "indexed"
        db_doc.chunk_count = total_chunks
        db.commit()
        logger.info(f"Background ingestion succeeded for doc {doc_id} with {total_chunks} chunks.")
        
        # Clean up temporary uploaded file from data/uploads/
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"Cleaned up temporary file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to remove temp file {filepath}: {e}")

    except Exception as e:
        db_doc.status = "failed"
        db.commit()
        logger.error(f"Background ingestion failed for doc {doc_id}: {str(e)}")
    finally:
        db.close()

@router.post("/upload", response_model=DocumentResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a document (PDF, TXT, MD).
    Steps:
    1. Validate file type (PDF, TXT, MD)
    2. Save file temporarily to data/uploads/
    3. Queue background text parsing, chunking, and FAISS indexing
    4. Return document details (id, filename, upload_date, chunk_count, status)
    """
    if not is_allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Only PDF, TXT, and MD files are supported.")

    filename = clean_filename(file.filename)
    
    # Ensure temporary upload directory exists
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    upload_dir_path = BASE_DIR / settings.UPLOAD_DIR
    os.makedirs(upload_dir_path, exist_ok=True)
    
    # Generate unique filepath
    filepath = upload_dir_path / filename
    counter = 1
    while os.path.exists(filepath):
        name, ext = os.path.splitext(filename)
        filepath = upload_dir_path / f"{name}_{counter}{ext}"
        counter += 1

    # Save file temporarily to data/uploads/
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save temp file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Could not save file to disk.")

    file_size = os.path.getsize(filepath)

    # Insert Document into database
    db_doc = DocumentORM(
        filename=os.path.basename(filepath),
        filepath=str(filepath),
        file_size=file_size,
        status="uploaded",
        chunk_count=0
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # Queue background task for text extraction and vector store ingestion
    from app.models.document import SessionLocal
    background_tasks.add_task(
        process_document_background,
        db_doc.id,
        str(filepath),
        db_doc.filename,
        SessionLocal
    )

    return db_doc

@router.get("/", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    """Retrieve all uploaded documents and their statuses."""
    return db.query(DocumentORM).all()

@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Delete a document, its associated chunk JSON file, and database entries."""
    db_doc = db.query(DocumentORM).filter(DocumentORM.id == doc_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # 1. Delete chunk JSON file if exists
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    chunk_file_path = BASE_DIR / settings.CHUNK_DIR / f"{doc_id}.json"
    if os.path.exists(chunk_file_path):
        try:
            os.remove(chunk_file_path)
            logger.info(f"Deleted chunk file: {chunk_file_path}")
        except Exception as e:
            logger.error(f"Failed to delete chunk file {chunk_file_path}: {e}")

    # 2. Delete database records (cascades memories)
    db.delete(db_doc)
    db.commit()
    return {"detail": "Document, chunks, and associated memories deleted successfully."}

@router.post("/query", response_model=PaginatedQueryResponse)
def query_knowledge_base(request: QueryRequest):
    """Query the vector database for top passages with optional filtering, pagination, and related chunks."""
    page = max(request.page or 1, 1)
    page_size = max(request.page_size or 5, 1)
    max_fetch = max(request.top_k or 50, page * page_size)

    # 1. Vector similarity search with filters
    results = vector_store.search(
        request.query,
        k=max_fetch,
        doc_types=request.doc_types,
        start_date=request.start_date,
        end_date=request.end_date
    )
    
    # 2. Enrich each result with metadata & related chunks from the same document
    enriched_items = []
    for r in results:
        doc_id = r.get("document_id", "")
        chunk_id = r.get("chunk_id", "")
        related = vector_store.get_related_chunks(document_id=doc_id, current_chunk_id=chunk_id, limit=2)
        
        enriched_items.append({
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "document_name": r["metadata"].get("filename", "Unknown Document"),
            "chunk": r["text"],
            "score": r["score"],
            "similarity": r.get("similarity", 0.0),
            "doc_type": r["metadata"].get("doc_type", "txt"),
            "timestamp": r["metadata"].get("timestamp", ""),
            "chunk_index": r["metadata"].get("chunk_index", 0),
            "total_chunks": r["metadata"].get("total_chunks", 1),
            "related_chunks": related
        })
        
    total = len(enriched_items)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # 3. Apply pagination slice
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_items = enriched_items[start_idx:end_idx]

    return {
        "items": paged_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.post("/{doc_id}/generate-insight", response_model=MemoryResponse)
async def generate_insight(doc_id: int, memory_in: MemoryCreate, db: Session = Depends(get_db)):
    """Generate insight using Modal LLM (or mock response fallback)."""
    db_doc = db.query(DocumentORM).filter(DocumentORM.id == doc_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Retrieve context from vector store using document name
    results = vector_store.search(f"summary of {db_doc.filename}", k=3)
    
    # Filter context chunks specifically belonging to this document
    relevant_chunks = [r["text"] for r in results if r["document_id"] == str(doc_id)]
    context = "\n".join(relevant_chunks) if relevant_chunks else "No context found."

    insight_type = memory_in.insight_type
    prompt = f"Analyze the following context from '{db_doc.filename}' and provide a {insight_type}:\n\nContext:\n{context}"

    llm_output = ""
    # Try calling the LLM client (Ollama/Modal) if an endpoint is configured
    if llm_client.base_url:
        try:
            chunks_input = [{"text": context, "filename": db_doc.filename, "document_id": str(doc_id)}]
            query_input = f"Analyze the context and generate a {insight_type}."
            logger.info(f"Requesting LLM insight ({insight_type}) via LLMClient...")
            res = llm_client.generate_answer(query_input, chunks_input)
            if res.get("source") == "llm":
                llm_output = res["answer"]
        except Exception as e:
            logger.error(f"Failed to generate LLM insight: {e}")

    # Fallback to local heuristic / mock agent response if LLM fails or is not configured
    if not llm_output.strip():
        logger.info("Using mock/local guardian response engine...")
        if insight_type == "summary":
            llm_output = (
                f"[Local Guardian Summary of {db_doc.filename}]\n"
                f"This document discusses concepts of knowledge indexing, storage architectures, and query processing. "
                f"Core sample passage matches: '{context[:150]}...'"
            )
        elif insight_type == "key_concept":
            llm_output = (
                f"[Key Concept Extraction]\n"
                f"- Concept A: Vector Similarity & FAISS Indexing\n"
                f"- Concept B: Local knowledge ingestion pipelines\n"
                f"- Concept C: Memory management policies"
            )
        else:
            llm_output = f"[Guardian Insight] Proactive alert generated based on content analysis:\n\n{context[:300]}..."

    # Save generated insight in SQLite memories table
    db_mem = MemoryORM(
        document_id=doc_id,
        insight_type=insight_type,
        content=llm_output
    )
    db.add(db_mem)
    db.commit()
    db.refresh(db_mem)

    return db_mem

@router.post("/query-stream")
async def query_knowledge_base_stream(request: QueryRequest):
    """Query the vector database and stream the answer along with matching document citations."""
    page = max(request.page or 1, 1)
    page_size = max(request.page_size or 5, 1)
    max_fetch = max(request.top_k or 50, page * page_size)

    # 1. Similarity search in vector store
    results = vector_store.search(
        request.query,
        k=max_fetch,
        doc_types=request.doc_types,
        start_date=request.start_date,
        end_date=request.end_date
    )
    
    # Resolve conversation_id
    conversation_id = request.conversation_id
    if not conversation_id:
        title = request.query[:30] + "..." if len(request.query) > 30 else request.query
        conversation_id = memory_manager.create_conversation(title=title)
    else:
        try:
            # Check if conversation exists
            memory_manager.get_messages(conversation_id)
        except ValueError:
            title = request.query[:30] + "..." if len(request.query) > 30 else request.query
            conversation_id = memory_manager.create_conversation(title=title)

    # Save user message to episodic memory
    try:
        memory_manager.add_message(conversation_id=conversation_id, role="user", content=request.query)
    except Exception as e:
        logger.error(f"Failed to log user query in stream: {e}")

    # If no results found, stream an empty set and error message
    if not results:
        fallback_msg = "I searched through your library, but I couldn't find any relevant passages matching your query."
        try:
            memory_manager.add_message(conversation_id=conversation_id, role="assistant", content=fallback_msg, sources=[])
        except Exception as e:
            logger.error(f"Failed to log fallback assistant response in stream: {e}")

        async def empty_generator():
            yield "data: " + json.dumps({
                "type": "citations",
                "citations": [],
                "conversation_id": conversation_id
            }) + "\n\n"
            yield "data: " + json.dumps({
                "type": "error",
                "message": fallback_msg
            }) + "\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_generator(), media_type="text/event-stream")

    # Format chunks for prompt and citations
    chunks = []
    enriched_items = []
    for r in results:
        doc_id = r.get("document_id", "")
        chunk_id = r.get("chunk_id", "")
        filename = r["metadata"].get("filename", "Unknown Document")
        text = r["text"]
        
        chunks.append({
            "document_id": doc_id,
            "filename": filename,
            "text": text
        })
        
        enriched_items.append({
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "document_name": filename,
            "chunk": text,
            "score": r["score"],
            "similarity": r.get("similarity", 0.0),
            "doc_type": r["metadata"].get("doc_type", "txt"),
            "timestamp": r["metadata"].get("timestamp", ""),
            "chunk_index": r["metadata"].get("chunk_index", 0),
            "total_chunks": r["metadata"].get("total_chunks", 1)
        })

    # Generator to stream results in SSE style
    async def sse_generator():
        # First send search citations / items metadata and the active conversation_id
        yield "data: " + json.dumps({
            "type": "citations",
            "citations": enriched_items,
            "conversation_id": conversation_id
        }) + "\n\n"
        
        # Then stream LLM tokens (limit context to top 5 chunks for faster inference & timeout prevention)
        accumulated_tokens = []
        async for token in llm_client.generate_answer_stream(request.query, chunks[:5]):
            accumulated_tokens.append(token)
            yield "data: " + json.dumps({
                "type": "token",
                "token": token
            }) + "\n\n"
        
        # Log assistant response to database on successful stream completion
        full_response = "".join(accumulated_tokens)
        if full_response.strip():
            # Prepare sources list
            sources = []
            for item in enriched_items[:5]:
                sources.append({
                    "document_id": item["document_id"],
                    "filename": item["document_name"],
                    "chunk_id": item["chunk_id"],
                    "text": item["chunk"][:200],
                    "similarity": item["similarity"]
                })
            try:
                memory_manager.add_message(conversation_id=conversation_id, role="assistant", content=full_response, sources=sources)
            except Exception as e:
                logger.error(f"Failed to log assistant message in stream completion: {e}")
            
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
