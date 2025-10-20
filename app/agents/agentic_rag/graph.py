import os
from typing import Any, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from ..common.callbacks import get_all_callbacks
from ..common.shared_state import State as SharedState
from langgraph.graph.message import Messages
from langchain_core.messages import ToolMessage
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables.config import RunnableConfig

from config.logger import logger
from config.settings import SETTINGS
from ..scheduler.graph import graph as subgraph
from ..common.checkpointer import checkpointer
from .tools import (
    ToRAGAssistant,
    CompleteOrEscalate,
    ToSchedulerAssistant,
)
from .nodes import (
    grade_documents,
    generate_answer,
    rewrite_question,
    create_entry_node,
    primary_assistant_node,
    rag_assistant_tool_node,
    generate_query_or_respond,
    primary_assistant_tool_node,
)


####################################
# ENABLE LANGGSMITH TRACING IF CONFIGURED
####################################

os.environ["LANGSMITH_TRACING"] = SETTINGS.LANGSMITH_TRACING
os.environ["LANGSMITH_API_KEY"] = SETTINGS.LANGSMITH_API_KEY
os.environ["LANGSMITH_PROJECT"] = SETTINGS.LANGSMITH_PROJECT
os.environ["LANGSMITH_ENDPOINT"] = SETTINGS.LANGSMITH_ENDPOINT

####################################
# UTILITIES
####################################


def _print_event(event: dict, _printed: set, max_length: int = 1500) -> str:
    p_dialog_state = event.get("p_dialog_state")
    s_dialog_state = event.get("s_dialog_state")

    p_state_str = p_dialog_state[-1] if p_dialog_state else "primary_assistant"
    s_state_str = s_dialog_state[-1] if s_dialog_state else "None"

    logger.info(f"Dialog State - Parent: {p_state_str}, Subgraph: {s_state_str}")

    message: Messages = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            logger.info(msg_repr)
            _printed.add(message.id)
            logger.info(message)
            return message.content
        return ""
    return ""


####################################
# DEFINE GRAPH
####################################

# builder = StateGraph(State)
builder = StateGraph(SharedState)

####################################
# AGENTIC RAG GRAPH
####################################
# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.


# def route_rag_assistant(state: State) -> str:
#     route = tools_condition(state)
#     if route == END:
#         return END
#     tool_calls = state["messages"][-1].tool_calls
#     did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
#     if did_cancel:
#         return "leave_skill"
#     return "generate_query_or_respond"


# Define the nodes we will cycle between
builder.add_node(
    "enter_generate_query_or_respond",
    create_entry_node("RAG Assistant", "generate_query_or_respond"),
)
builder.add_node("generate_query_or_respond", generate_query_or_respond)
builder.add_node("retrieve", rag_assistant_tool_node)
builder.add_node("rewrite_question", rewrite_question)
builder.add_node("generate_answer", generate_answer)

builder.add_edge("enter_generate_query_or_respond", "generate_query_or_respond")
# builder.add_edge(START, "generate_query_or_respond")


def route_generate_query_or_respond(state: SharedState) -> str:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    return "retrieve"


# builder.add_conditional_edges(
#     "generate_query_or_respond",
#     tools_condition,
#     {
#         "tools": "retrieve",
#         END: END,
#     },
# )

builder.add_conditional_edges(
    "generate_query_or_respond",
    route_generate_query_or_respond,
    ["retrieve", "leave_skill", END],
)

builder.add_conditional_edges(
    "retrieve",
    grade_documents,
)
builder.add_edge("generate_answer", END)
builder.add_edge("rewrite_question", "generate_query_or_respond")


###################################
# SUB GRAPH
###################################


# def route_scheduler_assistant(state: SharedState) -> str:
#     route = tools_condition(state)
#     if route == END:
#         return END
#     tool_calls = state["messages"][-1].tool_calls
#     did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
#     if did_cancel:
#         return "primary_assistant"
#     return END


builder.add_node(
    "enter_scheduler_assistant",
    create_entry_node("Scheduler Assistant", "scheduler_assistant"),
)
builder.add_node("scheduler_assistant", subgraph)
builder.add_edge("enter_scheduler_assistant", "scheduler_assistant")

# When subgraph completes, it should end (user can continue in next turn via START routing)
builder.add_edge("scheduler_assistant", END)
# builder.add_conditional_edges(
#     "scheduler_assistant", route_scheduler_assistant, ["primary_assistant", END]
# )


####################################
# GENERIC NODES AND EDGES
####################################
# This node will be shared for exiting all specialized assistants
def pop_dialog_state(state: SharedState) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                name="to_primary_assistant",  # Is it mandatory to add this name parameter as it is optional one?
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        # Pop from the parent dialog stack
        "p_dialog_state": "pop",
        "messages": messages,
    }


builder.add_node("leave_skill", pop_dialog_state)

builder.add_edge("leave_skill", "primary_assistant")

####################################
# PRIMARY ASSISTANT
####################################

builder.add_node("primary_assistant", primary_assistant_node)
builder.add_node("primary_assistant_tools", primary_assistant_tool_node)


def route_primary_assistant(state: SharedState, config: RunnableConfig) -> str:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == ToRAGAssistant.__name__:
            return "enter_generate_query_or_respond"
        elif tool_calls[0]["name"] == ToSchedulerAssistant.__name__:
            return "enter_scheduler_assistant"
        return "primary_assistant_tools"
    raise ValueError("Invalid route")


builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        END,
        "primary_assistant_tools",
        "enter_scheduler_assistant",
        "enter_generate_query_or_respond",
    ],
)


# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
def route_to_workflow(
    state: SharedState,
) -> Literal[
    "primary_assistant",
    "scheduler_assistant",
    "generate_query_or_respond",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("p_dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]


builder.add_conditional_edges(
    START,
    route_to_workflow,
    [
        "primary_assistant",
        "scheduler_assistant",
        "generate_query_or_respond",
    ],
)
builder.add_edge("primary_assistant_tools", "primary_assistant")

###################################
# COMPILE GRAPH
###################################

graph = builder.compile(checkpointer=checkpointer)

try:
    png_data = graph.get_graph(xray=True).draw_mermaid_png(
        draw_method=MermaidDrawMethod.API
    )
    with open("../workflow.png", "wb") as f:
        f.write(png_data)
except Exception as e:
    logger.error(e)


_printed: Any = set()


async def stream_graph_updates(user_input: str, thread_id: str) -> str:
    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "callbacks": get_all_callbacks(thread_id),
    }

    # response = graph.invoke({"messages": ("user", user_input)}, config=config)
    # return response["messages"][-1].content

    final_output = ""
    events = graph.stream(
        {"messages": ("user", user_input)},
        config=config,
        stream_mode="values",
        # subgraphs=True,
    )
    for event in events:
        final_output = _print_event(event, _printed)
    return final_output
