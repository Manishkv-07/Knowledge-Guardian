import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from app.config import settings, BASE_DIR
from app.models.document import DocumentORM, DocumentConnectionORM, SessionLocal
from app.services.vector_store import vector_store
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

VALID_RELATIONSHIP_TYPES = {"SIMILAR", "SUPPORTS", "CONTRADICTS", "EXTENDS", "ANSWERS", "RELATED"}


class ConnectionEvaluation(BaseModel):
    has_connection: bool = Field(
        default=False,
        description="True if a genuine, verifiable relationship exists between Document A and Document B."
    )
    relationship_type: Optional[str] = Field(
        default=None,
        description="One of: 'SIMILAR', 'SUPPORTS', 'CONTRADICTS', 'EXTENDS', 'ANSWERS', 'RELATED'"
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Concise 1-2 sentence explanation describing how the two passages connect."
    )
    evidence_source: Optional[str] = Field(
        default=None,
        description="A direct quote or factual snippet from Document A."
    )
    evidence_target: Optional[str] = Field(
        default=None,
        description="A direct quote or factual snippet from Document B."
    )
    confidence: Optional[float] = Field(
        default=0.8,
        description="Heuristic confidence score between 0.0 and 1.0 based on retrieval similarity and LLM evaluation (not an empirically calibrated probability)."
    )


class ConnectionEngine:
    """Proactive intelligence service that discovers and verifies cross-document connections."""

    def __init__(self):
        pass

    def evaluate_pair(
        self,
        doc_a_name: str,
        doc_a_text: str,
        doc_b_name: str,
        doc_b_text: str,
        retrieval_similarity: float = 0.5
    ) -> Optional[ConnectionEvaluation]:
        """Uses Groq to evaluate whether a verifiable relationship exists between two passages."""
        if not llm_client.is_groq_configured():
            logger.info("Groq is not configured; skipping LLM cross-document relationship evaluation.")
            return None

        prompt = (
            "You are the Personal Knowledge Guardian's Cross-Document Intelligence Engine.\n\n"
            "Analyze the following two passages from different documents in the user's research library:\n\n"
            f"--- PASSAGE A (from '{doc_a_name}') ---\n"
            f"{doc_a_text.strip()}\n\n"
            f"--- PASSAGE B (from '{doc_b_name}') ---\n"
            f"{doc_b_text.strip()}\n\n"
            "Task:\n"
            "Determine if there is a meaningful, factual cross-document connection between Passage A and Passage B.\n"
            "Valid relationship types:\n"
            "- SIMILAR: discusses a similar topic or approach.\n"
            "- SUPPORTS: provides evidence supporting a claim made in the other passage.\n"
            "- CONTRADICTS: provides evidence that genuinely conflicts with or opposes a claim.\n"
            "- EXTENDS: adds detail, depth, or developments to an existing idea.\n"
            "- ANSWERS: answers a question or limitation raised in the other passage.\n"
            "- RELATED: meaningfully related without fitting the above categories.\n\n"
            "STRICT RULES:\n"
            "1. ONLY state has_connection=true if BOTH passages provide direct evidence.\n"
            "2. Never classify passages as CONTRADICTS solely because they have low similarity. Only use CONTRADICTS for directly conflicting factual claims.\n"
            "3. If evidence is weak, coincidental, or trivial, output has_connection=false.\n"
            "4. Respond with valid JSON adhering to this exact schema:\n"
            "{\n"
            '  "has_connection": true/false,\n'
            '  "relationship_type": "SIMILAR" | "SUPPORTS" | "CONTRADICTS" | "EXTENDS" | "ANSWERS" | "RELATED",\n'
            '  "explanation": "Brief explanation",\n'
            '  "evidence_source": "Exact or close quote from Passage A",\n'
            '  "evidence_target": "Exact or close quote from Passage B",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}"
        )

        try:
            chat_model = llm_client._get_chat_model()
            if not chat_model:
                return None

            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="You are a strict, academically rigorous knowledge relationship analyzer. Output only valid JSON."),
                HumanMessage(content=prompt)
            ]
            response = chat_model.invoke(messages)
            raw_content = response.content if hasattr(response, "content") else str(response)

            # Extract JSON block
            json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if not json_match:
                logger.warning(f"Could not parse JSON from connection evaluation: {raw_content[:150]}")
                return None

            data = json.loads(json_match.group(0))
            evaluation = ConnectionEvaluation(**data)

            # Validate relationship type
            if evaluation.has_connection:
                rel = (evaluation.relationship_type or "").upper()
                if rel not in VALID_RELATIONSHIP_TYPES:
                    rel = "RELATED"
                evaluation.relationship_type = rel

                # Validate evidence is non-empty
                if not evaluation.evidence_source or not evaluation.evidence_target:
                    logger.info("Connection rejected: missing source or target evidence snippet.")
                    return None

                # Compute heuristic confidence score using retrieval similarity and LLM score (uncalibrated)
                heuristic_conf = round(min(1.0, max(0.1, 0.4 * float(retrieval_similarity) + 0.6 * float(evaluation.confidence or 0.8))), 3)
                evaluation.confidence = heuristic_conf
                return evaluation

            return None

        except Exception as e:
            logger.error(f"Error evaluating cross-document relationship: {e}")
            return None

    def discover_connections_for_document(self, document_id: int, db: Session = None) -> List[DocumentConnectionORM]:
        """Discovers cross-document connections between a newly ingested document and existing documents."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            doc = db.query(DocumentORM).filter(DocumentORM.id == document_id).first()
            if not doc:
                logger.warning(f"Document {document_id} not found in database for connection discovery.")
                return []

            # 1. Load chunks from data/chunks/{document_id}.json
            chunks_path = BASE_DIR / settings.CHUNK_DIR / f"{document_id}.json"
            if not chunks_path.exists():
                logger.warning(f"No chunk file found at {chunks_path}")
                return []

            with open(chunks_path, "r", encoding="utf-8") as f:
                new_chunks = json.load(f)

            if not new_chunks:
                return []

            # 2. Select representative chunks to bound LLM API calls (max 3 chunks)
            step = max(1, len(new_chunks) // 3)
            representative_chunks = new_chunks[::step][:3]

            candidate_pairs = []
            seen_pair_keys = set()

            # 3. Retrieve candidates from existing documents using vector search
            for source_chunk in representative_chunks:
                source_text = source_chunk.get("text", "")
                if not source_text.strip():
                    continue

                matches = vector_store.search(source_text, k=8, hybrid=True)
                for match in matches:
                    target_doc_id = str(match.get("document_id", ""))
                    # Exclude chunks from the same document!
                    if target_doc_id == str(document_id):
                        continue

                    # Require minimum similarity threshold
                    similarity = match.get("similarity", 0.0)
                    if similarity < 0.40:
                        continue

                    target_chunk_id = match.get("chunk_id", "")
                    source_chunk_id = source_chunk.get("id", "")
                    pair_key = tuple(sorted([source_chunk_id, target_chunk_id]))

                    if pair_key in seen_pair_keys:
                        continue
                    seen_pair_keys.add(pair_key)

                    candidate_pairs.append({
                        "source_chunk": source_chunk,
                        "target_match": match,
                        "similarity": similarity
                    })

            # Sort by similarity and bound to top 4 pairs
            candidate_pairs.sort(key=lambda p: p["similarity"], reverse=True)
            candidate_pairs = candidate_pairs[:4]

            if not candidate_pairs:
                logger.info(f"No cross-document candidate pairs found above similarity threshold for doc {document_id}.")
                return []

            logger.info(f"Evaluating {len(candidate_pairs)} candidate cross-document pairs for doc {document_id}...")

            created_connections = []

            for pair in candidate_pairs:
                s_chunk = pair["source_chunk"]
                t_match = pair["target_match"]
                sim = pair["similarity"]

                target_doc_id_str = t_match.get("document_id", "")
                try:
                    target_doc_id_int = int(target_doc_id_str)
                except ValueError:
                    continue

                # Ensure target document actually exists in database
                target_doc = db.query(DocumentORM).filter(DocumentORM.id == target_doc_id_int).first()
                if not target_doc:
                    continue

                source_chunk_id = str(s_chunk.get("id", ""))
                target_chunk_id = str(t_match.get("chunk_id", ""))

                # Deduplicate: check if connection already exists in either direction
                existing = db.query(DocumentConnectionORM).filter(
                    ((DocumentConnectionORM.source_chunk_id == source_chunk_id) & (DocumentConnectionORM.target_chunk_id == target_chunk_id)) |
                    ((DocumentConnectionORM.source_chunk_id == target_chunk_id) & (DocumentConnectionORM.target_chunk_id == source_chunk_id))
                ).first()

                if existing:
                    continue

                evaluation = self.evaluate_pair(
                    doc_a_name=doc.filename,
                    doc_a_text=s_chunk.get("text", ""),
                    doc_b_name=target_doc.filename,
                    doc_b_text=t_match.get("text", ""),
                    retrieval_similarity=sim
                )

                if evaluation and evaluation.has_connection:
                    conn = DocumentConnectionORM(
                        source_doc_id=doc.id,
                        target_doc_id=target_doc.id,
                        source_chunk_id=source_chunk_id,
                        target_chunk_id=target_chunk_id,
                        relationship_type=evaluation.relationship_type,
                        explanation=evaluation.explanation or f"Documents share concepts relating to {doc.filename} and {target_doc.filename}.",
                        evidence_source=evaluation.evidence_source,
                        evidence_target=evaluation.evidence_target,
                        source_filename=doc.filename,
                        target_filename=target_doc.filename,
                        source_page_number=s_chunk.get("metadata", {}).get("page_number"),
                        target_page_number=t_match.get("page_number"),
                        confidence=evaluation.confidence or round(sim, 3),
                        status="new",
                        created_at=datetime.utcnow()
                    )
                    db.add(conn)
                    created_connections.append(conn)

            if created_connections:
                db.commit()
                for c in created_connections:
                    db.refresh(c)
                logger.info(f"Discovered and persisted {len(created_connections)} new cross-document connections.")

            return created_connections

        except Exception as e:
            logger.error(f"Error during cross-document connection discovery: {e}")
            return []
        finally:
            if close_db:
                db.close()


connection_engine = ConnectionEngine()
