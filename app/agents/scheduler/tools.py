import uuid
import pytz
from typing import Annotated
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

import dateparser
from langgraph.types import Command
from langchain_core.tools import tool
from googleapiclient.errors import HttpError
from langchain_core.messages import ToolMessage
from langchain_core.tools.base import InjectedToolCallId

from .tool_schema import CreateEventToolArgs
from config.settings import SETTINGS
from config.constants import GOOGLE_CALENDAR_CONFIGS
from services.calendar_service import validate_event_slot, get_calendar_service

# from langchain_core.tools import tool
# from langchain_core.runnables import RunnableConfig


class ToCreateEventAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle creating a new event (scheduling a call)."""

    request: str = Field(
        description="Any necessary follow-up questions the create event assistant should clarify before proceeding with scheduling the call."
    )


class ToUpdateEventAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle updating an existing event (rescheduling or modifying details)."""

    request: str = Field(
        description="Any necessary follow-up questions the update event assistant should clarify before proceeding with modifying the event details."
    )


class ToCancelEventAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle canceling an existing event."""

    request: str = Field(
        description="Any necessary follow-up questions the cancel event assistant should clarify before proceeding with canceling the event."
    )


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str


###################################
# CREATE EVENT ASSISTANT TOOLS
###################################


@tool
def parse_nl_time_to_ist(nl_time: str) -> dict[str, str] | None:
    """
    Converts a natural language time string into ISO 8601 format in IST.

    Args:
        nl_time (str): Natural language expression of time (e.g., "tomorrow at 5pm").

    Returns:
        dict: {
            "iso_format": ISO 8601 datetime string in IST,
        }
        Returns None if parsing fails.
    """
    dt = dateparser.parse(
        nl_time,
        settings={
            "TIMEZONE": GOOGLE_CALENDAR_CONFIGS.DEFAULT_TIMEZONE.value,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )

    if not dt:
        return None

    ist = pytz.timezone(GOOGLE_CALENDAR_CONFIGS.DEFAULT_TIMEZONE.value)
    dt_ist = dt.astimezone(ist)

    return {"iso_format": dt_ist.isoformat()}


@tool
def check_slot_availability(start_iso: str) -> bool:
    """
    Checks if a user has any events in their Google Calendar during the given time range.

    Args:
        start_iso (str): Start time in ISO 8601 format (IST)

    Returns:
        bool: True if the time slot is available, False if busy.
    """
    try:
        start_obj = datetime.fromisoformat(start_iso)
        end_obj = start_obj + timedelta(minutes=SETTINGS.CALENDAR_SLOT_DURATION_MINUTES)
        end_iso = end_obj.isoformat()

        service = get_calendar_service()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_iso,
                timeMax=end_iso,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        # Filter only events created by this user
        my_events = [
            e
            for e in events
            if e.get("creator", {}).get("email") == SETTINGS.CALENDAR_ORGANIZER_EMAIL
        ]
        return len(my_events) == 0  # True if no events created by the user
    except HttpError:
        return False
    except Exception:
        return False


@tool(args_schema=CreateEventToolArgs)
def create_event(
    tool_call_id: Annotated[str, InjectedToolCallId],
    start: datetime,
    summary: str,
    description: str,
    attendees: list[str] | None = None,
    # location: str | None = None,
    # timezone: str | None = "Asia/Kolkata",
    # reminders: list[dict[str, Any]] | None = None,
) -> Command:
    """
    Creates an event on Google Calendar with Google Meet link and optional details.
    End time is automatically calculated using slot duration and validated.
    """
    service = get_calendar_service()

    end = start + timedelta(minutes=SETTINGS.CALENDAR_SLOT_DURATION_MINUTES)
    validate_event_slot(service, start, end)

    event = {
        "summary": summary,
        "location": GOOGLE_CALENDAR_CONFIGS.MEET_LOCATION.value,
        "description": description,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": GOOGLE_CALENDAR_CONFIGS.DEFAULT_TIMEZONE.value,
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": GOOGLE_CALENDAR_CONFIGS.DEFAULT_TIMEZONE.value,
        },
        "conferenceData": {  # Google Meet setup
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]

    # if reminders:
    #     event["reminders"] = {
    #         "useDefault": False,
    #         "overrides": reminders,  # e.g., [{"method": "email", "minutes": 30}]
    #     }

    created_event = (
        service.events()
        .insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",
            conferenceDataVersion=1,  # Required for Meet link
        )
        .execute()
    )

    dicts = {
        "event_link": created_event.get("htmlLink"),
        "meet_link": created_event.get("conferenceData", {})
        .get("entryPoints", [{}])[0]
        .get("uri"),
        "event_id": created_event.get("id"),
    }

    return Command(
        update={
            **dicts,
            "messages": [
                ToolMessage(
                    content=(
                        f"Great, your meeting is set up! Here's the link to join: {dicts['meet_link']}."
                        " You'll also receive the same details by email shortly."
                    ),
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


primary_assistant_tools = [
    ToCreateEventAssistant,
    ToUpdateEventAssistant,
    ToCancelEventAssistant,
]
create_event_assistant_tools = [
    create_event,
    parse_nl_time_to_ist,
    check_slot_availability,
]
update_event_assistant_tools = []
cancel_event_assistant_tools = []
