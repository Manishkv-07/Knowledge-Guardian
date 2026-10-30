import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from app.config import settings, BASE_DIR
from app.models.document import DocumentORM, FlashcardORM, SessionLocal
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)


class GeneratedFlashcardItem(BaseModel):
    question: str = Field(description="Clear, specific conceptual or factual question.")
    answer: str = Field(description="Accurate, concise answer grounded strictly in the source passage.")
    source_snippet: str = Field(description="Direct quotation from the text supporting this question and answer.")
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None


class FlashcardService:
    """Service for generating, managing, and scheduling source-grounded flashcards."""

    def generate_flashcards(
        self,
        document_id: int,
        chunk_ids: Optional[List[str]] = None,
        db: Session = None,
        count: int = 3
    ) -> List[FlashcardORM]:
        """Generates source-grounded flashcards for a document using Groq."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            doc = db.query(DocumentORM).filter(DocumentORM.id == document_id).first()
            if not doc:
                raise ValueError(f"Document with ID {document_id} not found.")

            # Load chunks from disk
            chunks_path = BASE_DIR / settings.CHUNK_DIR / f"{document_id}.json"
            if not chunks_path.exists():
                raise FileNotFoundError(f"Chunk file for document {document_id} not found.")

            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)

            if not all_chunks:
                return []

            # Filter chunks if specific chunk_ids were requested
            if chunk_ids:
                selected_chunks = [c for c in all_chunks if c.get("id") in set(chunk_ids)]
            else:
                # Take up to 4 representative chunks
                step = max(1, len(all_chunks) // 4)
                selected_chunks = all_chunks[::step][:4]

            if not selected_chunks:
                selected_chunks = all_chunks[:4]

            context_snippets = []
            for c in selected_chunks:
                cid = c.get("id", "")
                page = c.get("metadata", {}).get("page_number")
                text = c.get("text", "")[:400]
                header = f"[Chunk {cid}"
                if page:
                    header += f", Page {page}"
                header += "]"
                context_snippets.append(f"{header}:\n{text}")

            context_str = "\n\n".join(context_snippets)

            if not llm_client.is_groq_configured():
                logger.warning("Groq is not configured; cannot generate flashcards via AI.")
                return []

            prompt = (
                f"You are a study flashcard generator for the Personal Knowledge Guardian.\n\n"
                f"Document: '{doc.filename}'\n\n"
                f"Context Passages:\n{context_str}\n\n"
                f"Task:\n"
                f"Generate {count} high-quality, concept-testing flashcards based strictly on the passages above.\n\n"
                "STRICT RULES:\n"
                "1. Questions and answers must be strictly grounded in the provided passages.\n"
                "2. Provide an exact or close quotation in source_snippet as proof.\n"
                "3. Reference the chunk_id and page_number if provided.\n"
                "4. Output valid JSON adhering to this schema:\n"
                "[\n"
                "  {\n"
                '    "question": "Question text",\n'
                '    "answer": "Answer text",\n'
                '    "source_snippet": "Quote from text",\n'
                '    "chunk_id": "chunk_id_here",\n'
                '    "page_number": 1\n'
                "  }\n"
                "]"
            )

            chat_model = llm_client._get_chat_model()
            if not chat_model:
                return []

            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="You are an academic flashcard extraction assistant. Output only a valid JSON array."),
                HumanMessage(content=prompt)
            ]
            response = chat_model.invoke(messages)
            raw_content = response.content if hasattr(response, "content") else str(response)

            json_match = re.search(r'\[.*\]', raw_content, re.DOTALL)
            if not json_match:
                logger.warning(f"Could not parse JSON array for flashcards: {raw_content[:150]}")
                return []

            cards_data = json.loads(json_match.group(0))
            created_cards = []

            for item in cards_data:
                q = item.get("question", "").strip()
                a = item.get("answer", "").strip()
                if not q or not a:
                    continue

                card = FlashcardORM(
                    document_id=doc.id,
                    chunk_id=item.get("chunk_id") or selected_chunks[0].get("id"),
                    question=q,
                    answer=a,
                    source_snippet=item.get("source_snippet") or "",
                    filename=doc.filename,
                    page_number=item.get("page_number") or selected_chunks[0].get("metadata", {}).get("page_number"),
                    status="new",
                    interval_days=1,
                    ease_factor=2.5,
                    repetitions=0,
                    created_at=datetime.utcnow(),
                    next_review_date=datetime.utcnow()
                )
                db.add(card)
                created_cards.append(card)

            if created_cards:
                db.commit()
                for c in created_cards:
                    db.refresh(c)
                logger.info(f"Generated and persisted {len(created_cards)} flashcards for document {doc.filename}.")

            return created_cards

        finally:
            if close_db:
                db.close()

    def review_card(self, card_id: int, action: str, db: Session = None) -> FlashcardORM:
        """Applies deterministic SM-2 spaced repetition algorithm based on user rating.
        Actions: 'again' (1), 'hard' (2), 'good' (3), 'easy' (4).
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            card = db.query(FlashcardORM).filter(FlashcardORM.id == card_id).first()
            if not card:
                raise ValueError(f"Flashcard with ID {card_id} not found.")

            action = action.lower().strip()
            now = datetime.utcnow()

            interval = card.interval_days or 1
            ease = card.ease_factor or 2.5
            reps = card.repetitions or 0

            if action == "again":
                reps = 0
                interval = 1
                ease = max(1.3, ease - 0.2)
                card.status = "learning"
            elif action == "hard":
                interval = max(1, int(interval * 1.2))
                ease = max(1.3, ease - 0.15)
                card.status = "review"
            elif action == "good":
                if reps == 0:
                    interval = 1
                elif reps == 1:
                    interval = 6
                else:
                    interval = max(1, int(interval * ease))
                reps += 1
                card.status = "review"
            elif action == "easy":
                if reps == 0:
                    interval = 4
                elif reps == 1:
                    interval = 10
                else:
                    interval = max(1, int(interval * ease * 1.3))
                ease = min(3.0, ease + 0.15)
                reps += 1
                card.status = "review"
            else:
                raise ValueError(f"Invalid review action: '{action}'. Must be 'again', 'hard', 'good', or 'easy'.")

            card.interval_days = interval
            card.ease_factor = round(ease, 3)
            card.repetitions = reps
            card.next_review_date = now + timedelta(days=interval)

            db.commit()
            db.refresh(card)
            logger.info(f"Card {card_id} reviewed with action '{action}'. Next review in {interval} day(s).")
            return card

        finally:
            if close_db:
                db.close()


flashcard_service = FlashcardService()
