from typing import Annotated, Optional, Literal, Sequence, Any
from datetime import datetime
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str
    start: datetime
    timezone: str | None = "Asia/Kolkata"
    attendees: list[str] | None = None
    description: str | None = None
    location: str | None = None
    reminders: list[dict[str, Any]] | None = None
    dialog_state: Annotated[
        list[Literal["primary_assistant"]],
        update_dialog_stack,
    ]


default_state: State = {}
