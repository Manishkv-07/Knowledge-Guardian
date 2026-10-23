import sqlite3
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from app.models.document import DB_FILE_PATH

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self.db_path = DB_FILE_PATH
        self._init_conversation_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        # Enable foreign key cascade delete support in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_conversation_tables(self):
        """Create conversation and message tables if they don't exist"""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                role TEXT CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT,
                sources TEXT,  -- JSON array of source documents
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            """)
            conn.commit()
        logger.info("Initialized conversation and messages tables in SQLite database.")

    def create_conversation(self, title: str = "New Conversation") -> str:
        """Create a new conversation and return its ID"""
        conv_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, title, now, now)
            )
            conn.commit()
        logger.info(f"Created conversation: {conv_id} ({title})")
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str, sources: list = None) -> str:
        """Add a message to a conversation and update updated_at timestamp"""
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        sources_json = json.dumps(sources) if sources is not None else None
        
        with self._get_connection() as conn:
            # First check if conversation exists to throw error early
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
            if not cursor.fetchone():
                raise ValueError(f"Conversation with ID '{conversation_id}' does not exist.")
                
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, role, content, sources_json, now)
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )
            conn.commit()
        logger.info(f"Added message: {msg_id} (role={role}) to conversation {conversation_id}")
        return msg_id

    def get_conversations(self, limit: int = 20) -> List[Dict]:
        """Get all conversations with last message preview"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT m.content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) as last_message
                FROM conversations c
                ORDER BY c.updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conversations = []
            for row in rows:
                d = dict(row)
                # Preview truncation
                if d.get("last_message"):
                    last_msg = d["last_message"]
                    if len(last_msg) > 80:
                        d["last_message"] = last_msg[:77] + "..."
                else:
                    d["last_message"] = None
                conversations.append(d)
            return conversations

    def get_messages(self, conversation_id: str) -> List[Dict]:
        """Get all messages for a conversation in chronological order"""
        with self._get_connection() as conn:
            # Check if conversation exists
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
            if not cursor.fetchone():
                raise ValueError(f"Conversation with ID '{conversation_id}' does not exist.")
                
            cursor = conn.execute("""
                SELECT id, role, content, sources, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """, (conversation_id,))
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                d = dict(row)
                d["sources"] = json.loads(d["sources"]) if d.get("sources") else None
                messages.append(d)
            return messages

    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its messages (cascade delete)"""
        with self._get_connection() as conn:
            # Check if conversation exists
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
            if not cursor.fetchone():
                raise ValueError(f"Conversation with ID '{conversation_id}' does not exist.")
                
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
        logger.info(f"Deleted conversation: {conversation_id}")

    def rename_conversation(self, conversation_id: str, new_title: str):
        """Rename a conversation"""
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            # Check if conversation exists
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
            if not cursor.fetchone():
                raise ValueError(f"Conversation with ID '{conversation_id}' does not exist.")
                
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (new_title, now, conversation_id)
            )
            conn.commit()
        logger.info(f"Renamed conversation {conversation_id} to '{new_title}'")

    def seed_demo_data_if_empty(self):
        """Seed high-quality research documents and proactive memories if not already seeded"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Check if the demo document already exists
                cursor.execute("SELECT id FROM documents WHERE id = 101")
                if cursor.fetchone():
                    logger.info("Demo data already seeded. Skipping seed.")
                    return
            except sqlite3.OperationalError:
                logger.warning("Documents table does not exist. Cannot seed.")
                return

            logger.info("Seeding high-quality sample research documents and proactive memories for demo...")
            now = datetime.utcnow().isoformat()
            
            # 1. Insert Sample Document 1: Transformer Attention
            cursor.execute("""
                INSERT INTO documents (id, filename, filepath, file_size, upload_time, status, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                101, 
                "transformer_attention_mechanisms.pdf", 
                "data/uploads/transformer_attention_mechanisms.pdf", 
                124530, 
                now, 
                "indexed", 
                18
            ))
            
            # Insert stored insights for Doc 1
            cursor.execute("""
                INSERT INTO memories (id, document_id, insight_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                201,
                101,
                "summary",
                "This research paper provides a comprehensive retrospective on self-attention mechanisms in Transformer models. It outlines the transition from traditional recurrent architectures (LSTMs) to dense parallelized attention arrays, demonstrating how multi-head attention projects queries, keys, and values into separate spaces to jointly model dependencies across position alignments.",
                now
            ))
            cursor.execute("""
                INSERT INTO memories (id, document_id, insight_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                202,
                101,
                "key_concept",
                "### Core Cognitive Concepts Extracted:\n\n- **Self-Attention Alignment**: Models direct relationships between all token pairings in a sequence, resolving bottleneck limits found in sequential recurrence.\n- **Multi-Head Projection**: Linearly projects queries, keys, and values $h$ times in parallel to capture distinct representational patterns at various token positions.\n- **Complexity Scale**: Details quadratic memory complexity $\\mathcal{O}(n^2)$ and outlines modern sparse-attention alternatives for long-document context windows.",
                now
            ))

            # 2. Insert Sample Document 2: RAG Hallucinations
            cursor.execute("""
                INSERT INTO documents (id, filename, filepath, file_size, upload_time, status, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                102, 
                "combating_hallucinations_rag.pdf", 
                "data/uploads/combating_hallucinations_rag.pdf", 
                95400, 
                now, 
                "indexed", 
                12
            ))
            
            # Insert stored insights for Doc 2
            cursor.execute("""
                INSERT INTO memories (id, document_id, insight_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                203,
                102,
                "summary",
                "An analysis of Retrieval-Augmented Generation (RAG) pipelines and mitigation strategies for neural hallucinations. The study details how grounding large language models (LLMs) in structured vector contexts derived from document repositories constraints generation parameters, ensuring generated tokens remain factual and verifiable.",
                now
            ))
            cursor.execute("""
                INSERT INTO memories (id, document_id, insight_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                204,
                102,
                "key_concept",
                "### Core Cognitive Concepts Extracted:\n\n- **Grounding Contexts**: Feeding raw text chunks directly into the model prompt to guide token distribution.\n- **Vector Store Ingestion**: Utilizing encoders to index semantic embeddings in FAISS databases for high-speed similarity search.\n- **Verification Boundaries**: Enforcing prompt constraints that reject out-of-bounds queries.",
                now
            ))
            
            # 3. Create a seed conversation thread to show the sidebar working on startup
            # Check if conversation already exists to prevent duplicate primary key insertion
            cursor.execute("SELECT id FROM conversations WHERE id = 'seed-thread-id'")
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO conversations (id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, ("seed-thread-id", "Demo Study Session: Attention Mechanisms", now, now))
                
                cursor.execute("""
                    INSERT INTO messages (id, conversation_id, role, content, sources, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "seed-msg-1", 
                    "seed-thread-id", 
                    "user", 
                    "What is attention mechanism in transformers?", 
                    None, 
                    now
                ))
                
                cursor.execute("""
                    INSERT INTO messages (id, conversation_id, role, content, sources, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "seed-msg-2", 
                    "seed-thread-id", 
                    "assistant", 
                    "In Transformer architectures, the Attention mechanism (specifically Multi-Head Attention) projects the queries, keys, and values $h$ times with different, learned linear projections. This allows the model to jointly attend to information from different representation subspaces at different positions, improving representation learning and sequence modeling.",
                    json.dumps([{
                        "document_id": "101",
                        "filename": "transformer_attention_mechanisms.pdf",
                        "chunk_id": "chunk_attention_0",
                        "text": "Rather than performing a single attention function, Multi-Head Attention projects the queries, keys, and values h times...",
                        "similarity": 0.95
                    }]),
                    now
                ))
            
            conn.commit()
            logger.info("Demo seeding completed successfully.")

memory_manager = MemoryManager()
