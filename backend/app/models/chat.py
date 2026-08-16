from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict

class Conversation(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None

class Message(BaseModel):
    id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    sources: Optional[List[Dict]] = None
    created_at: datetime

class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"

class AddMessageRequest(BaseModel):
    role: str
    content: str
    sources: Optional[List[Dict]] = None

class ChatQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

class ChatQueryResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: List[Dict]
