import datetime
from fastapi import FastAPI, Query, Request
from sqlmodel import select, func
from db.db import SessionDep, create_db_and_tables
from db.model import EventCreate, Event, EventType, Severity, PaginatedEvents, Summary
from enum import Enum

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Assert 400 error for validation errors instead of 422 (FAST API default)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.post("/events", status_code=201)
@limiter.limit("100/minute")
def create_event(request: Request, event_in: EventCreate, session: SessionDep):
    event = Event.model_validate(event_in)   # EventCreate -> Event
    session.add(event)
    session.commit()
    session.refresh(event)
    return {"event_id": event.event_id}


@app.get("/events", response_model=PaginatedEvents)
def list_events(
  # # Example Req http://127.0.0.1:8000/events?event_type=motion_detected
    session: SessionDep,
    device_id: str | None = None,
    severity: Severity | None = None,
    event_type: EventType | None = None,
    from_: datetime.datetime | None = Query(default=None, alias="from"),
    to: datetime.datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    filters = []
    if device_id is not None:
        filters.append(Event.device_id == device_id)
    if severity is not None:
        filters.append(Event.severity == severity)
    if event_type is not None:
        filters.append(Event.event_type == event_type)
    if from_ is not None:
        filters.append(Event.timestamp >= from_)
    if to is not None:
        filters.append(Event.timestamp <= to)

    total = session.exec(
        select(func.count()).select_from(Event).where(*filters)
    ).one()

    events = session.exec(
        select(Event)
        .where(*filters)
        .order_by(Event.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedEvents(
        total=total, page=page, page_size=page_size, events=events,
    )


def _key(v):  # severity/event_type may come back as Enum or str
    return v.value if isinstance(v, Enum) else v


@app.get("/events/summary", response_model=Summary)
def summary(
    # Example Req http://127.0.0.1:8000/events/summary?from=2024&to=2026
    session: SessionDep,
    from_: datetime.datetime = Query(alias="from"),
    to: datetime.datetime = Query(alias="to"),
):
    window = [Event.timestamp >= from_, Event.timestamp <= to]

    sev_rows = session.exec(
        select(Event.severity, func.count()).where(*window).group_by(Event.severity)
    ).all()
    by_severity = {s.value: 0 for s in Severity}          # zero-fill
    for sev, count in sev_rows:
        by_severity[_key(sev)] = count

    type_rows = session.exec(
        select(Event.event_type, func.count()).where(*window).group_by(Event.event_type)
    ).all()
    by_event_type = {t.value: 0 for t in EventType}       # zero-fill
    for et, count in type_rows:
        by_event_type[_key(et)] = count

    top = session.exec(
        select(Event.device_id, func.count())
        .where(*window)
        .group_by(Event.device_id)
        .order_by(func.count().desc())
        .limit(1)
    ).first()
    most_active_device = top[0] if top else None

    total = sum(by_severity.values())
    high = by_severity.get("high", 0)
    high_severity_rate = round(high / total, 3) if total else 0.0

    return Summary(
        total_events=total,
        by_severity=by_severity,
        by_event_type=by_event_type,
        most_active_device=most_active_device,
        high_severity_rate=high_severity_rate,
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})