from typing import List, Optional, Annotated
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from langchain_core.tools.base import InjectedToolCallId


class CreateEventToolArgs(BaseModel):
    """Schema for creating a new Google Meet event."""

    start: datetime = Field(
        description="Start datetime of the event in ISO 8601 format (e.g., '2025-10-05T15:30:00').",
    )
    summary: str = Field(
        description="Short title or summary of the event (e.g., 'Discussion on project requirements').",
    )
    description: str = Field(
        description="Detailed purpose or agenda of the event provided by the user."
    )
    attendees: Optional[List[EmailStr]] = Field(
        default=None,
        description="List of attendee email addresses to be invited to the event.",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]
    # tool_call_id: str = Field(
    #     ...,
    #     description="Unique identifier for the tool call. Used internally to track the assistant's action request.",
    # )
    # timezone: Optional[str] = Field(
    #     "Asia/Kolkata",
    #     description="Timezone for the event. Defaults to 'Asia/Kolkata' if not provided.",
    # )
    # location: Optional[str] = Field(
    #     None,
    #     description="Location of the event if it's physical. Not required for Google Meet events.",
    # )
    # reminders: Optional[List[dict]] = Field(
    #     None,
    #     description="Optional reminders for the event, defined as a list of dictionaries (e.g., [{'method': 'email', 'minutes': 30}]).",
    # )
