from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.document import (
    get_db, DocumentORM, DocumentConnectionORM,
    ConnectionResponse, ConnectionUpdate, DiscoverConnectionsRequest
)
from app.services.connection_engine import connection_engine
from app.utils.helpers import logger

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("/", response_model=List[ConnectionResponse])
def list_connections(
    document_id: Optional[int] = Query(None, description="Filter by source or target document ID"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type (e.g. SIMILAR, SUPPORTS, CONTRADICTS)"),
    status: Optional[str] = Query(None, description="Filter by status (new, saved, dismissed)"),
    db: Session = Depends(get_db)
):
    """Retrieve cross-document connections with optional filtering."""
    query = db.query(DocumentConnectionORM)

    if document_id is not None:
        query = query.filter(
            (DocumentConnectionORM.source_doc_id == document_id) |
            (DocumentConnectionORM.target_doc_id == document_id)
        )

    if relationship_type:
        query = query.filter(DocumentConnectionORM.relationship_type == relationship_type.upper())

    if status:
        query = query.filter(DocumentConnectionORM.status == status.lower())
    else:
        # Default: show new and saved, hide dismissed unless explicitly requested
        query = query.filter(DocumentConnectionORM.status != "dismissed")

    query = query.order_by(DocumentConnectionORM.created_at.desc())
    return query.all()


@router.get("/graph")
def get_knowledge_graph(
    relationship_type: Optional[str] = Query(None, description="Filter edges by relationship type"),
    status: Optional[str] = Query(None, description="Filter edges by status: new, saved, dismissed"),
    db: Session = Depends(get_db)
):
    """Returns nodes (documents) and edges (verified connections) formatted for interactive graph visualization."""
    query = db.query(DocumentConnectionORM)
    if relationship_type:
        query = query.filter(DocumentConnectionORM.relationship_type == relationship_type.upper())
    if status:
        query = query.filter(DocumentConnectionORM.status == status.lower())
    else:
        query = query.filter(DocumentConnectionORM.status != "dismissed")

    connections = query.all()

    # Collect connected document IDs
    doc_ids = set()
    for c in connections:
        doc_ids.add(c.source_doc_id)
        doc_ids.add(c.target_doc_id)

    # Also include any other indexed documents so user sees the complete library landscape
    all_indexed = db.query(DocumentORM).filter(DocumentORM.status == "indexed").all()
    for d in all_indexed:
        doc_ids.add(d.id)

    docs = db.query(DocumentORM).filter(DocumentORM.id.in_(list(doc_ids))).all() if doc_ids else []

    nodes = [
        {
            "id": d.id,
            "label": d.filename,
            "chunk_count": d.chunk_count,
            "file_size": d.file_size,
            "status": d.status
        }
        for d in docs
    ]

    edges = [
        {
            "id": c.id,
            "source": c.source_doc_id,
            "target": c.target_doc_id,
            "relationship": c.relationship_type,
            "explanation": c.explanation,
            "evidence_source": c.evidence_source,
            "evidence_target": c.evidence_target,
            "source_filename": c.source_filename,
            "target_filename": c.target_filename,
            "source_page": c.source_page_number,
            "target_page": c.target_page_number,
            "confidence": c.confidence,
            "status": c.status
        }
        for c in connections
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }


@router.get("/{conn_id}", response_model=ConnectionResponse)
def get_connection(conn_id: int, db: Session = Depends(get_db)):
    """Retrieve a single cross-document connection with supporting evidence."""
    conn = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")
    return conn


@router.patch("/{conn_id}", response_model=ConnectionResponse)
def update_connection(conn_id: int, update: ConnectionUpdate, db: Session = Depends(get_db)):
    """Update connection status (e.g. save, dismiss) or notes."""
    conn = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    if update.status:
        conn.status = update.status.lower()
    if update.explanation:
        conn.explanation = update.explanation

    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{conn_id}")
def delete_connection(conn_id: int, db: Session = Depends(get_db)):
    """Delete a cross-document connection."""
    conn = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    db.delete(conn)
    db.commit()
    return {"detail": "Connection deleted successfully."}


@router.post("/discover", response_model=List[ConnectionResponse])
def discover_connections(req: DiscoverConnectionsRequest, db: Session = Depends(get_db)):
    """Trigger on-demand cross-document discovery for a specific document or all indexed documents."""
    if req.document_id:
        doc = db.query(DocumentORM).filter(DocumentORM.id == req.document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        new_conns = connection_engine.discover_connections_for_document(req.document_id, db=db)
        return new_conns
    else:
        # Discover across all indexed documents
        indexed_docs = db.query(DocumentORM).filter(DocumentORM.status == "indexed").all()
        all_new = []
        for d in indexed_docs:
            conns = connection_engine.discover_connections_for_document(d.id, db=db)
            all_new.extend(conns)
        return all_new
