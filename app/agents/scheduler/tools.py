from pydantic import BaseModel, Field

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


primary_assistant_tools = [
    ToCreateEventAssistant,
    ToUpdateEventAssistant,
    ToCancelEventAssistant,
]
create_event_assistant_tools = []
update_event_assistant_tools = []
cancel_event_assistant_tools = []
