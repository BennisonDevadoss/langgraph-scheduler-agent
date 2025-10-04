from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.messages.base import BaseMessage


from .tools import retriever_tool
from .state import State, default_state
from config.llms import llm
from .prompts import (
    generate_answer_assistant_prompt,
    document_greading_assistant_prompt,
    rewrite_user_prompt_assistant_prompt,
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
# GENERATE QUERY OR RESPOND ASSISTANT
###################################


def generate_query_or_respond(
    state: State, config: RunnableConfig
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

    response = llm.bind_tools([retriever_tool]).invoke(state["messages"])
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
    state: State,
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


def rewrite_question(state: State) -> dict[str, list[dict[str, Any]]]:
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


def generate_answer(state: State) -> dict[str, list]:
    """Generate an answer."""
    question = state["messages"][0].content
    context = state["messages"][-1].content
    prompt = generate_answer_assistant_prompt.format(question=question, context=context)
    response = llm.invoke([{"role": "user", "content": prompt}])
    return {"messages": [response]}


# generate_answer_assistant_runnable = generate_answer_assistant_prompt | llm
# generate_answer_assistant_node = Assistant(generate_answer_assistant_runnable)

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


retriever_tool_node = create_tool_node_with_fallback([retriever_tool])
