from typing import Annotated, Optional, Literal, Sequence, Any
from datetime import datetime
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from config.logger import logger


def update_p_dialog_stack(
    left: list[str], right: Optional[str | list[str]]
) -> list[str]:
    """Reducer for parent dialog state (p_dialog_state).
    
    Only parent nodes should update this. When subgraph returns its state,
    we ignore it to prevent subgraph from modifying parent's routing.
    """
    if right is None:
        return left

    # If subgraph returns a list, ignore it - keep parent's state
    if isinstance(right, list):
        if right != left:
            logger.debug(
                f"[p_dialog_state] Subgraph returned {right}, keeping parent: {left}"
            )
        return left

    # String operations: push or pop
    if right == "pop":
        return left[:-1]

    # Push new dialog state
    return left + [right]


def update_s_dialog_stack(
    left: list[str], right: Optional[str | list[str]]
) -> list[str]:
    """Reducer for subgraph dialog state (s_dialog_state).
    
    Only subgraph nodes should update this. When subgraph returns its state,
    we accept it so parent can see subgraph's internal routing.
    """
    if right is None:
        return left

    # If subgraph returns a list, accept it - this is the subgraph's internal state
    if isinstance(right, list):
        if right != left:
            logger.debug(
                f"[s_dialog_state] Subgraph returned {right}, updating from {left}"
            )
        return right  # Accept subgraph's state

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
        update_p_dialog_stack,
    ]
    s_dialog_state: Annotated[
        list[Literal["primary_assistant", "create_event_assistant"]],
        update_s_dialog_stack,
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
