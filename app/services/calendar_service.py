import os
import uuid
from typing import Any
from datetime import datetime, timedelta

from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from config.settings import SETTINGS
from exceptions.custom_errors import (
    ConflictException,
    BadRequestException,
    UnauthorizedException,
)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_FILE = "./creds/token.json"
CREDENTIALS_FILE = "./creds/credentials.json"


def authenticate_user() -> str:
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        # return "Already authenticated"
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        return "Authentication successful"


def get_calendar_service() -> Any:
    """
    Loads saved token or refreshes it, returns Google Calendar service instance.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise UnauthorizedException(
                "User not authenticated. Call /v1/calendar/auth first."
            )

    service = build("calendar", "v3", credentials=creds)
    return service


def is_time_slot_free_for_me(
    service: Any,
    start: datetime,
    end: datetime,
    organizer_email: str,  # oragnizer_email should be mine
) -> bool:
    """
    Checks if the primary calendar is free for events created by the authenticated user.
    Returns True if free, False if a conflicting event exists.
    """
    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        # Filter only events created by this user
        my_events = [
            e for e in events if e.get("creator", {}).get("email") == organizer_email
        ]

        return len(my_events) == 0  # True if no events created by me in this range

    except HttpError as e:
        raise e


def validate_event_slot(service: Any, start: datetime, end: datetime) -> None:
    """Validates that the event start time is within working hours and computes end time."""
    # Define working hours
    work_start = start.replace(
        hour=SETTINGS.CALENDAR_WORKING_HOURS_START, minute=0, second=0, microsecond=0
    )
    work_end = start.replace(
        hour=SETTINGS.CALENDAR_WORKING_HOURS_END, minute=0, second=0, microsecond=0
    )

    # Check working hours
    if not (work_start <= start < work_end) or not (work_start < end <= work_end):
        raise BadRequestException(
            f"Event must be within working hours: "
            f"{SETTINGS.CALENDAR_WORKING_HOURS_START}:00 - "
            f"{SETTINGS.CALENDAR_WORKING_HOURS_END}:00"
        )

    # Check for conflicts in the organizer's calendar
    if not is_time_slot_free_for_me(
        service, start, end, SETTINGS.CALENDAR_ORGANIZER_EMAIL
    ):
        raise ConflictException(
            "The requested time slot overlaps with an existing event"
        )


def create_event(
    summary: str,
    start: datetime,
    timezone: str | None = "Asia/Kolkata",
    attendees: list[str] | None = None,
    description: str | None = None,
    location: str | None = None,
    reminders: list[dict[str, Any]] | None = None,
) -> dict:
    """
    Creates an event on Google Calendar with Google Meet link and optional details.
    End time is automatically calculated using slot duration and validated.
    """
    service = get_calendar_service()

    end = start + timedelta(minutes=SETTINGS.CALENDAR_SLOT_DURATION_MINUTES)
    validate_event_slot(service, start, end)

    event = {
        "summary": summary,
        "location": location or "",
        "description": description or "",
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
        "conferenceData": {  # Google Meet setup
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]

    if reminders:
        event["reminders"] = {
            "useDefault": False,
            "overrides": reminders,  # e.g., [{"method": "email", "minutes": 30}]
        }

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

    return {
        "event_link": created_event.get("htmlLink"),
        "meet_link": created_event.get("conferenceData", {})
        .get("entryPoints", [{}])[0]
        .get("uri"),
        "event_id": created_event.get("id"),
    }


# uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib
# https://developers.google.com/workspace/calendar/api/v3/reference/events?authuser=1#resource-representations
