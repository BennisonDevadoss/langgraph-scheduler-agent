from typing import Any, Callable

from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from .state import State, default_state
from .prompts import primary_assistant_prompt, create_event_assistant_prompt
from config.llms import llm
from .tools import (
    CompleteOrEscalate,
    primary_assistant_tools,
    create_event_assistant_tools,
)


class Assistant:
    def __init__(self, runnable: Runnable) -> None:
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        while True:
            # configuration = config.get("configurable", {})
            state = {**default_state, **state}

            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)  # noqa: W503
                and not result.content[0].get("text")  # noqa: W503
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


###################################
# SUPERVISOR ASSISTANT
###################################

primary_assistant_runnable = primary_assistant_prompt | llm.bind_tools(
    primary_assistant_tools
)
primary_assistant_node = Assistant(primary_assistant_runnable)

###################################
# CREATE EVENT ASSISTANT
###################################

create_event_assistant_runnable = create_event_assistant_prompt | llm.bind_tools(
    create_event_assistant_tools + [CompleteOrEscalate]
)  # noqa: W503
create_event_assistant_node = Assistant(create_event_assistant_runnable)

###################################
# ENTRY NODE
###################################


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    name=new_dialog_state,  # NOTE: IS IT MANDATORY TO ADD THIS NAME PARAMETER AS IT IS OPTIONAL ONE?
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " and the booking, update, other other action is not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node


###################################
# TOOL NODE
###################################


def handle_tool_error(state: State) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


primary_assistant_tool_node = create_tool_node_with_fallback(primary_assistant_tools)
create_event_assistant_tool_node = create_tool_node_with_fallback(
    create_event_assistant_tools
)
