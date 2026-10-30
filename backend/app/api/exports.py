import io
import csv
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.models.document import (
    get_db, DocumentORM, DocumentConnectionORM, FlashcardORM, MemoryORM
)
from app.services.memory_manager import memory_manager

router = APIRouter(prefix="/exports", tags=["exports"])


def _safe_export_filename(name: str, ext: str) -> str:
    """Sanitize filename to prevent header injection or unsafe characters."""
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    clean = clean.strip('_')[:50]
    return f"{clean or 'export'}.{ext}"


@router.get("/document/{doc_id}/markdown")
def export_document_summary_markdown(doc_id: int, db: Session = Depends(get_db)):
    """Export document metadata, stored insights, and connected cross-document links as a structured Markdown file."""
    doc = db.query(DocumentORM).filter(DocumentORM.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    memories = db.query(MemoryORM).filter(MemoryORM.document_id == doc_id).all()
    connections = db.query(DocumentConnectionORM).filter(
        (DocumentConnectionORM.source_doc_id == doc_id) | (DocumentConnectionORM.target_doc_id == doc_id)
    ).all()

    upload_str = doc.upload_time.strftime("%Y-%m-%d %H:%M UTC") if doc.upload_time else "Unknown"
    lines = [
        f"# Research Summary: {doc.filename}",
        f"",
        f"- **Document ID**: `{doc.id}`",
        f"- **Ingestion Date**: {upload_str}",
        f"- **File Size**: {doc.file_size} bytes",
        f"- **Indexed Chunks**: {doc.chunk_count}",
        f"- **Status**: `{doc.status}`",
        f"",
        f"---",
        f"",
        f"## Stored Memory Units & Insights",
        f""
    ]

    if not memories:
        lines.append("*No synthesized memory units stored yet for this document.*")
    else:
        for idx, mem in enumerate(memories, 1):
            title = mem.insight_type.replace('_', ' ').title()
            date_str = mem.created_at.strftime("%Y-%m-%d %H:%M") if mem.created_at else ""
            lines.append(f"### {idx}. {title} ({date_str})")
            lines.append("")
            lines.append(mem.content)
            lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## Connected Cross-Document Relationships",
        f""
    ])

    if not connections:
        lines.append("*No cross-document connections established with other library papers.*")
    else:
        for c in connections:
            other_name = c.target_filename if c.source_doc_id == doc_id else c.source_filename
            src_p = f", p. {c.source_page_number}" if c.source_page_number else ""
            tgt_p = f", p. {c.target_page_number}" if c.target_page_number else ""
            lines.append(f"### [{c.relationship_type}] {other_name}")
            lines.append(f"**Explanation**: {c.explanation}")
            lines.append(f"")
            lines.append(f"> **Evidence in {c.source_filename}{src_p}**:")
            lines.append(f"> \"{c.evidence_source}\"")
            lines.append(f"")
            lines.append(f"> **Evidence in {c.target_filename}{tgt_p}**:")
            lines.append(f"> \"{c.evidence_target}\"")
            lines.append(f"")

    content = "\n".join(lines)
    filename = _safe_export_filename(f"{doc.filename}_summary", "md")
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/connections/markdown")
def export_connections_markdown(
    status: Optional[str] = Query(None, description="Filter by status: new, saved, dismissed"),
    db: Session = Depends(get_db)
):
    """Export all established cross-document connections and dual-passage evidence quotes as Markdown."""
    query = db.query(DocumentConnectionORM)
    if status:
        query = query.filter(DocumentConnectionORM.status == status.lower())
    else:
        query = query.filter(DocumentConnectionORM.status != "dismissed")

    connections = query.order_by(DocumentConnectionORM.created_at.desc()).all()

    lines = [
        f"# Personal Knowledge Guardian: Cross-Document Discoveries",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"Total Connections Exported: {len(connections)}",
        f"",
        f"---",
        f""
    ]

    for c in connections:
        src_p = f" (p. {c.source_page_number})" if c.source_page_number else ""
        tgt_p = f" (p. {c.target_page_number})" if c.target_page_number else ""
        lines.append(f"## {c.source_filename} ↔ {c.target_filename}")
        lines.append(f"- **Relationship**: `{c.relationship_type}`")
        lines.append(f"- **Confidence Score**: {round((c.confidence or 0.8) * 100)}%")
        lines.append(f"- **Status**: `{c.status}`")
        lines.append(f"- **Explanation**: {c.explanation}")
        lines.append(f"")
        lines.append(f"> **Source Passage** ({c.source_filename}{src_p}):")
        lines.append(f"> \"{c.evidence_source}\"")
        lines.append(f"")
        lines.append(f"> **Target Passage** ({c.target_filename}{tgt_p}):")
        lines.append(f"> \"{c.evidence_target}\"")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    content = "\n".join(lines)
    filename = _safe_export_filename("cross_document_connections", "md")
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/flashcards/csv")
def export_flashcards_csv(
    document_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Export flashcards in Anki-compatible CSV format (Front/Question, Back/Answer, Citation, Document)."""
    query = db.query(FlashcardORM)
    if document_id:
        query = query.filter(FlashcardORM.document_id == document_id)

    cards = query.order_by(FlashcardORM.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Question", "Answer", "Source Citation", "Document", "Page", "Status", "Interval Days", "Ease Factor"])

    for c in cards:
        writer.writerow([
            c.question,
            c.answer,
            c.source_snippet or "",
            c.filename,
            c.page_number or "",
            c.status,
            c.interval_days or 1,
            c.ease_factor or 2.5
        ])

    csv_data = output.getvalue()
    filename = _safe_export_filename("guardian_flashcards", "csv")
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/research-notes/markdown")
def export_research_notes_markdown(db: Session = Depends(get_db)):
    """Export full synthesis of all indexed library documents, active pattern memories, and saved connections."""
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    docs = db.query(DocumentORM).filter(DocumentORM.status == "indexed").all()
    connections = db.query(DocumentConnectionORM).filter(DocumentConnectionORM.status == "saved").all()
    patterns = memory_manager.get_pattern_memories(status="active")

    lines = [
        f"# Personal Knowledge Guardian: Master Research Compendium",
        f"Export Timestamp: {now_str}",
        f"",
        f"## Library Summary",
        f"- Total Indexed Documents: {len(docs)}",
        f"- Active Cognitive Patterns: {len(patterns)}",
        f"- Verified Saved Connections: {len(connections)}",
        f"",
        f"---",
        f"",
        f"## 1. Active Cognitive Research Patterns",
        f""
    ]

    if not patterns:
        lines.append("*No recurring cognitive topic patterns tracked yet.*")
    else:
        for p in patterns:
            lines.append(f"### Topic: {p['topic']} (Observed {p['frequency']}x)")
            lines.append(f"{p['observation']}")
            docs_json = p.get("source_documents")
            if docs_json:
                try:
                    doc_list = json.loads(docs_json) if isinstance(docs_json, str) else docs_json
                    lines.append(f"- Relevant Papers: {', '.join(doc_list)}")
                except Exception:
                    pass
            lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 2. Indexed Document Repository & Extracted Memories",
        f""
    ])

    for d in docs:
        lines.append(f"### 📄 {d.filename}")
        lines.append(f"- Chunks: {d.chunk_count} | Size: {d.file_size} bytes")
        memories = db.query(MemoryORM).filter(MemoryORM.document_id == d.id).all()
        if memories:
            for m in memories:
                lines.append(f"#### Insight: {m.insight_type.title()}")
                lines.append(m.content)
                lines.append("")
        else:
            lines.append("*No custom insights generated for this document.*")
        lines.append("")

    content = "\n".join(lines)
    filename = _safe_export_filename("guardian_master_research_notes", "md")
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
