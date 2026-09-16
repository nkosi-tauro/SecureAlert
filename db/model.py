'''Event model for the SecureAlert application.'''

import datetime
from typing import Any
from sqlmodel import Field, SQLModel, Column, JSON
from enum import Enum

class EventType(str, Enum):
    motion_detected = "motion_detected"
    intrusion_alert = "intrusion_alert"
    camera_offline = "camera_offline"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class EventBase(SQLModel):
    '''SQLModel model for the Event table in the database.'''
    device_id: str = Field(min_length=3, max_length=64, index=True)
    event_type: EventType = Field(index=True)
    severity: Severity = Field(index=True)
    timestamp: datetime.datetime = Field(index=True)

class Event(EventBase, table=True):
    '''SQL Table for the Event model.'''
    event_id: int | None = Field(default=None, primary_key=True)
    event_metadata: dict[str, Any] | None = Field(
      default=None,
      sa_column=Column("metadata", JSON),
    )


class EventCreate(EventBase):
    '''Post Event model for creating new events.'''

class EventGet(EventBase):
    '''Get Event model for returning events to the client.'''
    event_id: int

class PaginatedEvents(SQLModel):
    '''Paginated response model for returning events to the client.'''
    total: int
    page: int
    page_size: int
    events: list[EventGet]

class Summary(SQLModel):
    total_events: int
    by_severity: dict[str, int]
    by_event_type: dict[str, int]
    most_active_device: str | None
    high_severity_rate: float

