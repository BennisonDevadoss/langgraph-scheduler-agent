from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from services import conversation_service, chat_service
from config.logger import logger
from config.database import get_db
from schemas.conversation_schema import (
    ConversationCreate,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationResponse,
    ConversationWithMessages,
)

conversation_router = APIRouter(prefix="/conversations", tags=["Conversations"])


@conversation_router.post(
    "/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    params: ConversationCreate,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """Create a new conversation"""
    try:
        conversation = conversation_service.create_conversation(db, params.session_id)
        return ConversationResponse.model_validate(conversation)
    except Exception as e:
        logger.exception(e)
        raise e


@conversation_router.get(
    "/session/{session_id}", response_model=list[ConversationResponse]
)
async def get_session_conversations(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    """Get all conversations for a session"""
    try:
        conversations = conversation_service.get_conversations_by_session(
            db, session_id
        )
        return [ConversationResponse.model_validate(conv) for conv in conversations]
    except Exception as e:
        logger.exception(e)
        raise e


@conversation_router.get(
    "/{conversation_uuid}", response_model=ConversationWithMessages
)
async def get_conversation(
    conversation_uuid: UUID,
    db: Session = Depends(get_db),
) -> ConversationWithMessages:
    """Get a conversation with its messages"""
    try:
        conversation = conversation_service.get_conversation_by_uuid(
            db, conversation_uuid
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationWithMessages.model_validate(conversation)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(e)
        raise e


@conversation_router.delete("/{conversation_uuid}")
async def delete_conversation(
    conversation_uuid: UUID,
    session_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a conversation"""
    try:
        conversation_service.delete_conversation(db, conversation_uuid, session_id)
        return {"message": "Conversation deleted successfully"}
    except Exception as e:
        logger.exception(e)
        raise e


@conversation_router.post(
    "/{conversation_uuid}/chat", response_model=ChatMessageResponse
)
async def send_chat_message(
    conversation_uuid: UUID,
    params: ChatMessageRequest,
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """Send a message and get bot response"""
    try:
        # Get conversation
        conversation = conversation_service.get_conversation_by_uuid(
            db, conversation_uuid
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Verify session_id matches
        if conversation.session_id != params.session_id:
            raise HTTPException(
                status_code=403, detail="Unauthorized access to conversation"
            )

        # Save user message
        _ = conversation_service.add_message(
            db, conversation.id, "user", params.message
        )

        # Get all messages for context
        messages = conversation_service.get_conversation_messages(db, conversation.id)
        message_history = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        # Generate bot response using existing chat service
        # Using a simple thread_id based on conversation_id
        thread_id = f"conv_{conversation.id}"
        bot_response = await chat_service.generate_scheduler_chat_completion(
            message_history, thread_id
        )

        # Save bot message
        bot_message = conversation_service.add_message(
            db, conversation.id, "bot", bot_response
        )

        return ChatMessageResponse(
            message_id=bot_message.id,
            bot_response=bot_response,
            conversation_uuid=conversation.uuid,
        )
    except HTTPException:
        raise e
    except Exception as e:
        logger.exception(e)
        raise e
