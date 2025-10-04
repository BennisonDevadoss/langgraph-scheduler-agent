from typing import Any

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain.tools.retriever import create_retriever_tool

from config.vector_db import vector_db


@tool()
def retriever_tool(query: str, _: RunnableConfig) -> Any:
    """Search and return information about user query"""

    retriever_tool = create_retriever_tool(
        vector_db.vector_store.as_retriever(),
        "retriver_tool",
        "Search and return information about user query",
    )
    return retriever_tool.invoke(input=query)
