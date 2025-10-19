from datetime import datetime, timezone

from uuid import UUID
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config.models import Conversation, Message
from exceptions.custom_errors import NotFoundException


def create_conversation(db: Session, session_id: str) -> Conversation:
    """Create a new conversation for a session"""
    conversation = Conversation(
        session_id=session_id,
        title=f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_by_id(db: Session, conversation_id: int) -> Conversation | None:
    """Get a conversation by internal ID"""
    return (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.deleted_at.is_(None))
        .first()
    )


def get_conversation_by_uuid(
    db: Session, conversation_uuid: UUID
) -> Conversation | None:
    """Get a conversation by UUID"""
    return (
        db.query(Conversation)
        .filter(
            Conversation.uuid == conversation_uuid, Conversation.deleted_at.is_(None)
        )
        .first()
    )


def get_conversations_by_session(db: Session, session_id: str) -> list[Conversation]:
    """Get all conversations for a session"""
    return (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id, Conversation.deleted_at.is_(None)
        )
        .order_by(desc(Conversation.updated_at))
        .all()
    )


def get_or_create_conversation(
    db: Session, conversation_id: int | None, session_id: str
) -> Conversation:
    """Get existing conversation or create a new one"""
    if conversation_id:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            raise NotFoundException(f"Conversation {conversation_id} not found")
        # Verify session_id matches
        if conversation.session_id != session_id:
            raise NotFoundException("Conversation not found for this session")
        return conversation

    # Create new conversation
    return create_conversation(db, session_id)


def add_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
    """Add a message to a conversation"""
    message = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(message)

    # Update conversation's updated_at timestamp
    conversation = get_conversation_by_id(db, conversation_id)
    if conversation:
        conversation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(message)
    return message


def get_conversation_messages(db: Session, conversation_id: int) -> list[Message]:
    """Get all messages for a conversation"""
    return (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id, Message.deleted_at.is_(None)
        )
        .order_by(Message.created_at)
        .all()
    )


def delete_conversation(db: Session, conversation_uuid: UUID, session_id: str) -> bool:
    """Soft delete a conversation"""
    conversation = get_conversation_by_uuid(db, conversation_uuid)
    if not conversation:
        raise NotFoundException("Conversation not found")

    # Verify session_id matches
    if conversation.session_id != session_id:
        raise NotFoundException("Conversation not found for this session")

    conversation.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return True
