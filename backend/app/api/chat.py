from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.models.chat import Conversation, Message, CreateConversationRequest
from app.services.memory_manager import memory_manager

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/conversations", response_model=List[Conversation])
async def get_all_conversations(limit: int = 20):
    """List all conversations with preview"""
    try:
        conversations = memory_manager.get_conversations(limit=limit)
        return conversations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/conversations", response_model=dict)
async def create_new_conversation(request: CreateConversationRequest):
    """Create a new conversation"""
    try:
        title = request.title or "New Conversation"
        conversation_id = memory_manager.create_conversation(title=title)
        return {"id": conversation_id, "title": title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations/{conversation_id}", response_model=List[Message])
async def get_conversation_history(conversation_id: str):
    """Get full conversation history"""
    try:
        messages = memory_manager.get_messages(conversation_id)
        return messages
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/conversations/{conversation_id}")
async def rename_chat_conversation(conversation_id: str, title: str = Query(..., description="New title of the conversation")):
    """Rename conversation"""
    try:
        memory_manager.rename_conversation(conversation_id, title)
        return {"detail": "Conversation renamed successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/conversations/{conversation_id}")
async def delete_chat_conversation(conversation_id: str):
    """Delete conversation"""
    try:
        memory_manager.delete_conversation(conversation_id)
        return {"detail": "Conversation deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
