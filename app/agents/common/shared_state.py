from typing import Annotated, Optional, Literal, Sequence, Any
from datetime import datetime
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from config.logger import logger


def update_dialog_stack(left: list[str], right: Optional[str | list[str]]) -> list[str]:
    """Push or pop the state.

    When a subgraph returns, it may pass the entire list back.
    In that case, we should use the subgraph's value as-is (replace, not append).
    """
    if right is None:
        return left

    # If subgraph returns a list, it's the complete state - use it as-is
    if isinstance(right, list):
        # If it's the same as left, no change needed (avoid unnecessary updates)
        if right == left:
            return left
        # Otherwise, the subgraph is returning its internal state - keep parent's state
        # This prevents subgraph's internal dialog state from polluting parent
        logger.debug(
            f"Subgraph returned different state: {right}, keeping parent: {left}"
        )
        return left

    # String operations: push or pop
    if right == "pop":
        return left[:-1]

    # Push new dialog state
    return left + [right]


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str | None
    start: datetime | None
    timezone: str | None
    attendees: list[str] | None
    description: str | None
    location: str | None
    reminders: list[dict[str, Any]] | None
    # Create Event Responses
    event_id: str | None
    meet_link: str | None
    event_link: str | None
    p_dialog_state: Annotated[
        list[
            Literal[
                "primary_assistant", "scheduler_assistant", "generate_query_or_respond"
            ]
        ],
        update_dialog_stack,
    ]
    s_dialog_state: Annotated[
        list[Literal["primary_assistant", "create_event_assistant"]],
        update_dialog_stack,
    ]


default_state: State = {
    "start": None,
    "summary": None,
    "location": None,
    "timezone": None,
    "reminders": None,
    "attendees": None,
    "description": None,
    # Create Event Responses
    "event_id": None,
    "meet_link": None,
    "event_link": None,
}
