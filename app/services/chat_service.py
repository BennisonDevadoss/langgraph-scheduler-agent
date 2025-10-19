# services/chat_service.py
# import openai  # Example using OpenAI API, replace with your LLM if needed
from typing import List

from agents.agentic_rag.graph import stream_graph_updates as stream_rag_graph_updates
from agents.scheduler.graph import (
    stream_graph_updates as stream_scheduler_graph_updates,
)


# Connects the agentic_rag assistant to the scheduler agent using LangGraph subgraphs
async def generate_rag_chat_completion(
    messages: List[dict],
    thread_id: str,
) -> str:
    """
    Generates a chat completion from the LLM based on the provided messages.
    """
    return await stream_rag_graph_updates(messages[-1]["content"], thread_id)


async def generate_scheduler_chat_completion(
    messages: List[dict], thread_id: str
) -> str:
    """
    Generates a chat completion from the LLM based on the provided messages.
    """
    return await stream_scheduler_graph_updates(messages[-1]["content"], thread_id)
