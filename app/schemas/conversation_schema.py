from datetime import datetime

from uuid import UUID
from pydantic import BaseModel


# Message schemas
class MessageBase(BaseModel):
    role: str
    content: str


class MessageResponse(MessageBase):
    id: int
    conversation_id: int  # Internal ID, not exposed in conversation endpoints
    created_at: datetime

    class Config:
        from_attributes = True


# Conversation schemas
class ConversationCreate(BaseModel):
    session_id: str


class ConversationResponse(BaseModel):
    uuid: UUID  # Public-facing UUID
    session_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationResponse):
    messages: list[MessageResponse]

    class Config:
        from_attributes = True


# Chat request/response schemas
class ChatMessageRequest(BaseModel):
    message: str
    session_id: str


class ChatMessageResponse(BaseModel):
    message_id: int
    bot_response: str
    conversation_uuid: UUID  # Return UUID instead of int ID
