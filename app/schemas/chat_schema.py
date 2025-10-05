from pydantic import BaseModel


# Pydantic model for the request
class RAGChatRequestParams(BaseModel):
    messages: list[dict]  # Example: [{"role": "user", "content": "Hello"}]
    thread_id: str
    captcha_token: str | None = None
    collection_name: str


class SchedulerChatRequestParams(BaseModel):
    messages: list[dict]  # Example: [{"role": "user", "content": "Hello"}]
    thread_id: str
    captcha_token: str | None = None


# Pydantic model for the response
class ChatResponse(BaseModel):
    message: str
