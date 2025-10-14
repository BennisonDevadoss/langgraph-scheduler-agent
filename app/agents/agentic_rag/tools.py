from typing import Any

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain.tools.retriever import create_retriever_tool

from config.vector_db import vector_db


class ToRAGAssistant(BaseModel):
    """Transfers work to a specialized assistant that retrieves and answers user queries using Bennison’s portfolio knowledge base."""

    query: str = Field(
        description="The user's question or topic that should be answered using the RAG (Retrieval-Augmented Generation) system."
    )


class ToSchedulerAssistant(BaseModel):
    """Transfers work to a specialized assistant responsible for managing calls — creating, updating, or canceling scheduled events."""

    action: str = Field(
        description="Specifies the scheduling action type. One of: 'create', 'update', or 'cancel'."
    )
    # request: str = Field(description="Details related to the scheduling action.") # if it is there this `primary_assistant` asks for date and time.


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str


@tool()
def retriever_tool(query: str, _: RunnableConfig) -> Any:
    """Search and return information about user query"""

    retriever_tool = create_retriever_tool(
        vector_db.vector_store.as_retriever(),
        "retriver_tool",
        "Search and return information about user query",
    )
    return retriever_tool.invoke(input=query)


primary_assistant_tools = [
    ToRAGAssistant,
    ToSchedulerAssistant,
]

rag_assistant_tools = [retriever_tool]
