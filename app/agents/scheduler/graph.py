from typing import Literal, Any

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from langgraph.graph.message import Messages
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables.config import RunnableConfig

from .state import State
from config.logger import logger

# from ..common.callbacks import get_all_callbacks
from ..common.checkpointer import checkpointer
from .tools import (
    CompleteOrEscalate,
    ToCreateEventAssistant,
    ToUpdateEventAssistant,
    ToCancelEventAssistant,
)
from .nodes import (
    create_entry_node,
    primary_assistant_node,
    primary_assistant_tool_node,
    create_event_assistant_node,
    create_event_assistant_tool_node,
)

####################################
# UTILITIES
####################################


def _print_event(event: dict, _printed: set, max_length: int = 1500) -> str:
    current_state = event.get("dialog_state")
    if current_state:
        logger.info(f"Currently in: {current_state[-1]}")
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

builder = StateGraph(State)

###################################
# CREATE EVENT ASSISTANT
###################################

# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.


def route_create_event_assistant(state: State) -> str:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    return "create_event_assistant_tools"


builder.add_node(
    "enter_create_event",
    create_entry_node("Create Event Assistant", "create_event_assistant"),
)
builder.add_node("create_event_assistant", create_event_assistant_node)
builder.add_node("create_event_assistant_tools", create_event_assistant_tool_node)

builder.add_edge("enter_create_event", "create_event_assistant")
builder.add_conditional_edges(
    "create_event_assistant",
    route_create_event_assistant,
    ["create_event_assistant_tools", "leave_skill", END],
)
builder.add_edge("create_event_assistant_tools", "create_event_assistant")

####################################
# PRIMARY ASSISTANT
####################################

builder.add_node("primary_assistant", primary_assistant_node)
builder.add_node("primary_assistant_tools", primary_assistant_tool_node)


def route_primary_assistant(state: State, _: RunnableConfig) -> str:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == ToCreateEventAssistant.__name__:
            return "enter_create_event"
        elif tool_calls[0]["name"] == ToUpdateEventAssistant.__name__:
            return "enter_update_event"
        elif tool_calls[0]["name"] == ToCancelEventAssistant.__name__:
            return "enter_cancel_event"
        return "primary_assistant_tools"
    raise ValueError("Invalid route")


builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        "enter_create_event",
        "enter_update_event",
        "enter_cancel_event",
        "primary_assistant_tools",
        END,
    ],
)


# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
def route_to_workflow(
    state: State,
) -> Literal[
    "primary_assistant",
    "create_event_assistant",
    # "update_event_assistant",
    # "cancel_event_assistant",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
        # return END
    return dialog_state[-1]


# builder.add_edge(START, "primary_assistant")
builder.add_conditional_edges(
    START,
    route_to_workflow,
    [
        "primary_assistant",
        "create_event_assistant",
        # "update_event_assistant",
        # "cancel_event_assistant",
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
    with open("./assets/scheduler-agent-graph.png", "wb") as f:
        f.write(png_data)
except Exception as e:
    logger.error(e)
    pass


_printed: Any = set()


async def stream_graph_updates(user_input: str, thread_id: str | None = None) -> str:
    config = {
        "configurable": {
            # Checkpoints are accessed by thread_id
            "thread_id": thread_id,
        },
        # "callbacks": get_all_callbacks(thread_id),
    }

    # response = graph.invoke({"messages": ("user", user_input)}, config=config)
    # return response["messages"][-1].content

    final_output = ""
    events = graph.stream(
        {"messages": ("user", user_input)}, config=config, stream_mode="values"
    )
    for event in events:
        final_output = _print_event(event, _printed)
    return final_output
