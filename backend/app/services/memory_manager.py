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

memory_manager = MemoryManager()
