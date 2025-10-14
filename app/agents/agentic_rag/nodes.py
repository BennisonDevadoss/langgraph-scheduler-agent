from typing import Any, Literal, Sequence, Callable

from pydantic import BaseModel, Field
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.messages.base import BaseMessage


# from .state import State, default_state
from config.llms import llm
from ..common.shared_state import State as SharedState, default_state
from .tools import (
    retriever_tool,
    CompleteOrEscalate,
    rag_assistant_tools,
    primary_assistant_tools,
)
from .prompts import (
    rag_assistant_prompt,
    primary_assistant_prompt,
    generate_answer_assistant_prompt,
    document_greading_assistant_prompt,
    rewrite_user_prompt_assistant_prompt,
)


class Assistant:
    def __init__(self, runnable: Runnable) -> None:
        self.runnable = runnable

    def __call__(self, state: SharedState, config: RunnableConfig) -> dict[str, Any]:
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
# RAG ASSISTANT
###################################

rag_assistant_runnable = rag_assistant_prompt | llm.bind_tools(
    []
)  # need to work on here.
rag_assistant_node = Assistant(rag_assistant_runnable)

###################################
# GENERATE QUERY OR RESPOND ASSISTANT
###################################


def generate_query_or_respond(
    state: SharedState, config: RunnableConfig
) -> dict[str, list[BaseMessage]]:
    """Call the model to generate a response based on the current state. Given
    the question, it will decide to retrieve using the retriever tool, or simply respond to the user.
    """

    # collection_name = (
    #     config["configurable"]["collection_name"]
    #     if "collection_name" in config["configurable"]
    #     else None
    # )
    # retriver_tools = get_all_retriver_tools(collection_name)

    runnable = rag_assistant_prompt | llm.bind_tools(
        [retriever_tool, CompleteOrEscalate]
    )
    response = runnable.invoke(state)
    return {"messages": [response]}


# generate_query_or_respond_runnable = llm.bind_tools([])
# generate_query_or_respond_node = Assistant(generate_query_or_respond_runnable)


###################################
# DOCUMENT GREADING ASSISTANT
###################################


class GradeDocuments(BaseModel):
    """Grade documents using a binary score for relevance check."""

    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


def grade_documents(
    state: SharedState,
) -> Literal["generate_answer", "rewrite_question"]:
    """Determine whether the retrieved documents are relevant to the question."""
    question = state["messages"][0].content
    context = state["messages"][-1].content

    prompt = document_greading_assistant_prompt.format(
        question=question, context=context
    )
    response: GradeDocuments = llm.with_structured_output(GradeDocuments).invoke(
        [{"role": "user", "content": prompt}]
    )
    score = response.binary_score

    if score == "yes":
        return "generate_answer"
    else:
        return "rewrite_question"


# document_greading_assistant_runnable = (
#     document_greading_assistant_prompt | llm.with_structured_output(GradeDocuments)
# )
# document_greading_assistant_node = Assistant(document_greading_assistant_runnable)


###################################
# REWRITE QUESTION ASSISTANT
###################################


def get_latest_human_question(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    # there is no possible of returning empty string
    return ""


def rewrite_question(state: SharedState) -> dict[str, list[dict[str, Any]]]:
    """Rewrite the original user question."""
    messages = state["messages"]
    question = get_latest_human_question(messages)
    prompt = rewrite_user_prompt_assistant_prompt.format(question=question)
    response = llm.invoke([{"role": "user", "content": prompt}])
    return {"messages": [{"role": "user", "content": response.content}]}


# rewrite_question_assistant_runnable = rewrite_user_prompt_assistant_prompt | llm
# rewrite_question_assistant_node = Assistant(rewrite_question_assistant_runnable)

###################################
# GENERATE ANSWER ASSISTANT
###################################


def generate_answer(state: SharedState) -> dict[str, list]:
    """Generate an answer."""
    question = state["messages"][0].content
    context = state["messages"][-1].content
    prompt = generate_answer_assistant_prompt.format(question=question, context=context)
    response = llm.invoke([{"role": "user", "content": prompt}])
    return {"messages": [response]}


# generate_answer_assistant_runnable = generate_answer_assistant_prompt | llm
# generate_answer_assistant_node = Assistant(generate_answer_assistant_runnable)


###################################
# ENTRY NODE
###################################


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: SharedState) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    name=new_dialog_state,  # IS IT MANDATORY TO ADD THIS NAME PARAMETER AS IT IS OPTIONAL ONE?
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " and the booking, update, other other action is not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            # Push onto parent dialog stack via update function by returning a string
            "p_dialog_state": new_dialog_state,
        }

    return entry_node


###################################
# TOOL NODE
###################################


def handle_tool_error(state: SharedState) -> dict:
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


rag_assistant_tool_node = create_tool_node_with_fallback(rag_assistant_tools)
primary_assistant_tool_node = create_tool_node_with_fallback(primary_assistant_tools)
