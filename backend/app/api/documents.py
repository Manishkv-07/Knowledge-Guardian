import os
import shutil
import httpx
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.config import settings
from app.models.document import (
    get_db, DocumentORM, MemoryORM, DocumentResponse, MemoryResponse,
    QueryRequest, QueryResponse, MemoryCreate
)
from app.services.ingestion import ingestion_service
from app.services.vector_store import vector_store
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

@router.post("/query", response_model=List[QueryResponse])
def query_knowledge_base(request: QueryRequest):
    """Query the vector database for top K relevant passages."""
    results = vector_store.search(request.query, k=request.top_k)
    
    # Map results to QueryResponse structure
    query_responses = []
    for r in results:
        query_responses.append({
            "chunk": r["text"],
            "score": r["score"],
            "document_name": r["metadata"]["filename"]
        })
        
    return query_responses

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
    # Try calling Modal if configured
    if settings.MODAL_ENDPOINT_URL:
        try:
            logger.info(f"Calling Modal LLM endpoint at {settings.MODAL_ENDPOINT_URL}...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.MODAL_ENDPOINT_URL,
                    headers={"Authorization": f"Bearer {settings.MODAL_API_KEY}"} if settings.MODAL_API_KEY else {},
                    json={"prompt": prompt, "max_tokens": 256},
                    timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json()
                    llm_output = data.get("text", data.get("choices", [{}])[0].get("text", ""))
                else:
                    logger.error(f"Modal API error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Failed to connect to Modal LLM: {e}")

    # Fallback to local heuristic / mock agent response if Modal fails or is not set
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
