from typing import Any

from langchain_core.runnables import Runnable, RunnableConfig

from .state import State, default_state


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
