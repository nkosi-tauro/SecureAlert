import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from db.db import get_session 
from main import app 


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    app.state.limiter.enabled = False     
    yield TestClient(app)
    app.dependency_overrides.clear()


def _event(**over):
    base = {
        "device_id": "cam-south-01",
        "event_type": "motion_detected",
        "severity": "low",
        "timestamp": "2024-11-15T03:22:10Z",
        "metadata": {"zone": "entrance"},
    }
    base.update(over)
    return base


# ---- POST ----

def test_post_returns_201_and_id(client):
    r = client.post("/events", json=_event())
    assert r.status_code == 201
    assert "event_id" in r.json()

def test_post_missing_field_rejected(client):
    body = _event()
    del body["severity"]
    assert client.post("/events", json=body).status_code == 400

def test_post_device_id_too_short(client):
    assert client.post("/events", json=_event(device_id="a")).status_code == 400

def test_post_bad_timestamp(client):
    assert client.post("/events", json=_event(timestamp="Jan 2025")).status_code == 400

def test_post_bad_enum(client):
    assert client.post("/events", json=_event(severity="urgent")).status_code == 400


# ---- GET list ----

def test_list_sorted_desc_and_total_is_full_set(client):
    for i, ts in enumerate(["2024-11-15T01:00:00Z",
                            "2024-11-15T03:00:00Z",
                            "2024-11-15T02:00:00Z"]):
        client.post("/events", json=_event(timestamp=ts))

    r = client.get("/events?page_size=2")
    body = r.json()
    assert body["total"] == 3                    # full set, not the page
    assert len(body["events"]) == 2              # page_size honored
    ts = [e["timestamp"] for e in body["events"]]
    assert ts == sorted(ts, reverse=True)        # newest first

def test_list_filter_by_device(client):
    client.post("/events", json=_event(device_id="cam-north-09"))
    client.post("/events", json=_event(device_id="cam-south-01"))
    body = client.get("/events?device_id=cam-north-09").json()
    assert body["total"] == 1

