from fastapi import APIRouter, HTTPException, Request, Depends

from services import chat_service
from config.logger import logger
from dependencies.captcha import verify_captcha
from dependencies.fingerprint import verify_session_fingerprint
from schemas.chat_schema import (
    ChatResponse,
    RAGChatRequestParams,
    SchedulerChatRequestParams,
)

chat_router = APIRouter(prefix="/chat", tags=["Chat"])


@chat_router.post("/rag/web", response_model=ChatResponse)
async def rag_chat_completion(request: RAGChatRequestParams) -> ChatResponse:
    """
    Endpoint to generate chat completions from the LLM based on user input messages.
    """
    try:
        completion = await chat_service.generate_rag_chat_completion(
            request.messages, request.collection_name, request.thread_id
        )
        return ChatResponse(message=completion)
    except HTTPException as e:
        logger.exception(e)
        raise e


@chat_router.post("/scheduler/web", response_model=ChatResponse)
async def schduler_chat_completion(request: SchedulerChatRequestParams) -> ChatResponse:
    """
    Endpoint to generate chat completions from the LLM based on user input messages.
    """
    try:
        completion = await chat_service.generate_scheduler_chat_completion(
            request.messages, request.thread_id
        )
        return ChatResponse(message=completion)
    except HTTPException as e:
        logger.exception(e)
        raise e


# TODO: The below API is currently under development. Do not use it in production.
# This experimental route demonstrates approaches for securing an API,
# including rate limiting and access control strategies.
@chat_router.post(
    "/secure/web",
    dependencies=[Depends(verify_captcha), Depends(verify_session_fingerprint)],
    response_model=ChatResponse,
)
async def chat_completion_web(
    request: Request,  # Request parameter need to be present, if using `slowapi` plugin
    params: SchedulerChatRequestParams,
) -> ChatResponse:
    try:
        completion = await chat_service.generate_scheduler_chat_completion(
            params.messages, params.collection_name, params.thread_id
        )
        return ChatResponse(message=completion)
    except HTTPException as e:
        logger.exception(e)
        raise e
