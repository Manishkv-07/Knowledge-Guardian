from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.document import (
    get_db, DocumentORM, FlashcardORM,
    FlashcardResponse, FlashcardCreate, FlashcardUpdate,
    FlashcardReviewRequest, GenerateFlashcardsRequest
)
from app.services.flashcard_service import flashcard_service
from app.utils.helpers import logger

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get("/", response_model=List[FlashcardResponse])
def list_flashcards(
    document_id: Optional[int] = Query(None, description="Filter by source document ID"),
    due_only: bool = Query(False, description="Filter only cards due for spaced repetition review"),
    db: Session = Depends(get_db)
):
    """Retrieve flashcards with optional document and review due filters."""
    query = db.query(FlashcardORM)

    if document_id is not None:
        query = query.filter(FlashcardORM.document_id == document_id)

    if due_only:
        now = datetime.utcnow()
        query = query.filter(FlashcardORM.next_review_date <= now)

    query = query.order_by(FlashcardORM.next_review_date.asc())
    return query.all()


@router.get("/{card_id}", response_model=FlashcardResponse)
def get_flashcard(card_id: int, db: Session = Depends(get_db)):
    """Retrieve a single flashcard."""
    card = db.query(FlashcardORM).filter(FlashcardORM.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found.")
    return card


@router.post("/", response_model=FlashcardResponse)
def create_flashcard(card_in: FlashcardCreate, db: Session = Depends(get_db)):
    """Manually create a new study flashcard linked to a document."""
    doc = db.query(DocumentORM).filter(DocumentORM.id == card_in.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Referenced document not found.")

    card = FlashcardORM(
        document_id=card_in.document_id,
        chunk_id=card_in.chunk_id,
        question=card_in.question.strip(),
        answer=card_in.answer.strip(),
        source_snippet=card_in.source_snippet or "",
        filename=card_in.filename or doc.filename,
        page_number=card_in.page_number,
        status="new",
        interval_days=1,
        ease_factor=2.5,
        repetitions=0,
        created_at=datetime.utcnow(),
        next_review_date=datetime.utcnow()
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=FlashcardResponse)
def update_flashcard(card_id: int, card_up: FlashcardUpdate, db: Session = Depends(get_db)):
    """Update question, answer, or source snippet of an existing flashcard."""
    card = db.query(FlashcardORM).filter(FlashcardORM.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found.")

    if card_up.question:
        card.question = card_up.question.strip()
    if card_up.answer:
        card.answer = card_up.answer.strip()
    if card_up.source_snippet is not None:
        card.source_snippet = card_up.source_snippet

    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}")
def delete_flashcard(card_id: int, db: Session = Depends(get_db)):
    """Delete a flashcard."""
    card = db.query(FlashcardORM).filter(FlashcardORM.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found.")

    db.delete(card)
    db.commit()
    return {"detail": "Flashcard deleted successfully."}


@router.post("/{card_id}/review", response_model=FlashcardResponse)
def review_flashcard(card_id: int, req: FlashcardReviewRequest, db: Session = Depends(get_db)):
    """Submit a spaced repetition review rating ('again', 'hard', 'good', 'easy')."""
    try:
        updated = flashcard_service.review_card(card_id, req.action, db=db)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate", response_model=List[FlashcardResponse])
def generate_flashcards(req: GenerateFlashcardsRequest, db: Session = Depends(get_db)):
    """Generate source-grounded flashcards for a document using Groq."""
    try:
        cards = flashcard_service.generate_flashcards(
            document_id=req.document_id,
            chunk_ids=req.chunk_ids,
            count=req.count or 3,
            db=db
        )
        return cards
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Flashcard generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Flashcard generation failed: {str(e)}")
