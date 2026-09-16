<h1 align="center">SecureAlert</h1>

<p align="center">A production-minded backend service for ingesting, storing, and querying security events from edge devices (cameras, sensors).</p>

<p align="center">
  <a href="#dart-about">About</a> &#xa0; | &#xa0;
  <a href="#rocket-technologies">Stack &amp; Rationale</a> &#xa0; | &#xa0;
  <a href="#checkered_flag-starting">Getting Started</a> &#xa0; | &#xa0;
  <a href="#mag-api">API</a> &#xa0; | &#xa0;
  <a href="#thought_balloon-assumptions">Assumptions</a> &#xa0; | &#xa0;
  <a href="#hourglass-with-more-time">With More Time</a>
</p>

## :dart: About

SecureAlert receives security event data from edge devices, persists it, and exposes a small HTTP API for a dashboard to query. It provides three endpoints: event ingestion, a filtered/paginated event list, and a time-windowed summary with aggregate statistics.

Validation is enforced at the API boundary (Pydantic), the persistence model is kept deliberately thin, and aggregation is pushed into SQL rather than computed in Python.

## :sparkles: Features

:heavy_check_mark: **Event ingestion** with full validation required fields, ISO 8601 timestamps, `device_id` length bounds, and enum-constrained `event_type`/`severity`;\
:heavy_check_mark: **Filtered, paginated queries** by device, severity, type, and time range, sorted newest-first;\
:heavy_check_mark: **Time-windowed summary** totals, per-severity and per-type breakdowns (zero-filled), most active device, and high-severity rate;\
:heavy_check_mark: **Per-IP rate limiting** using SlowAPI, with a 100/minute default limit;\
:heavy_check_mark: **Test suite** covering validation, pagination, ordering, and sparse/empty-window edge cases.

## :rocket: Technologies

- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [SQLModel](https://sqlmodel.tiangolo.com/) — ORM + Pydantic models over SQLite
- [SQLite](https://www.sqlite.org/) — embedded database (WAL mode)
- [SlowAPI](https://slowapi.readthedocs.io/en/latest/) — rate limiting
- [uv](https://docs.astral.sh/uv/) — dependency management
- [Pytest](https://docs.pytest.org/en/stable/) — tests

### Why these choices

**Python + FastAPI** — FastAPI is simple, fast and easy to use without boilerplate or package overhead. It has first-class support for Pydantic validation, which is a requirement of the spec.

**SQLite** — In Memory DB, no need for external dependencies as no data persistence is required. Chose SQL over NoSQL because the data is structured and relational, and the summary endpoint is an aggregation query that is more naturally expressed in SQL.

## :white_check_mark: Requirements

[uv](https://docs.astral.sh/uv/) installed. uv provisions a matching Python interpreter automatically, so a system Python is not required.

## :checkered_flag: Starting

```bash
# Clone
git clone https://github.com/nkosi-tauro/SecureAlert
cd SecureAlert

# Install uv (if needed)
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies and run
uv sync
uv run fastapi dev

# Run tests
uv run pytest
```

The server starts on `http://127.0.0.1:8000`. Interactive API docs (Swagger UI) are at `http://127.0.0.1:8000/docs` — the easiest way to exercise the endpoints.

## :mag: API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/events` | Ingest an event. Returns `201` and the created event ID. |
| `GET`  | `/events` | List events. Optional filters: `device_id`, `severity`, `event_type`, `from`, `to`; `page`, `page_size` (max 100). Sorted newest-first. |
| `GET`  | `/events/summary` | Aggregate stats over a required `from`/`to` window. |

### Example `POST /events` request
Endpoint: http://127.0.0.1:8000/events
```json
{
  "device_id": "camera-1",
  "timestamp": "2025-01-01T12:00:00Z",
  "event_type": "motion_detected",
  "severity": "high"
}
```
### Example `GET /events` request
Endpoint: http://127.0.0.1:8000/events?device_id=cam-south-01
- add additional query params as needed: `severity`, `event_type`, `from`, `to`, `page`, `page_size`

### Example `GET /events/summary` request
Endpoint: http://127.0.0.1:8000/events/summary?from=2024&to=2026


## :thought_balloon: Assumptions

- **Validation errors return `400`** per the spec, via a handler that maps FastAPI's default `422`.
- **`high_severity_rate` is `0.0` for an empty window** — a defensible reading of "0 of 0" rather than an error.
- **`most_active_device` breaks ties arbitrarily** — `ORDER BY count DESC LIMIT 1` does not define an ordering among equal counts; acceptable at this scale.
- **Rate limiting is keyed per IP.** For devices behind a shared gateway, per-`device_id` limiting would map better to the threat model, but `device_id` lives in the request body and isn't available to the limiter's key function.

## :hourglass: With More Time

- **Keyset pagination** for the list endpoint. Offset pagination is correct here but scans-and-discards skipped rows and can shift items across pages under concurrent inserts; a `WHERE timestamp < :cursor` keyset approach (supported by the existing timestamp index) scales better over large history.
- **Postgres** as the migration path once the service needs to scale beyond a single process/host — both SQLite and the in-memory rate-limit store are single-process by design. **Redis** would back the rate limiter under multiple workers.
- **Per-device rate limiting and auth** — edge devices should authenticate (API keys/mTLS), which would also give a natural per-device rate-limit key.
- **Structured logging and a `/health` endpoint** for observability in a real deployment.
- **A composite `(device_id, timestamp)` index** if device-scoped time queries turn out to dominate in practice.

## :memo: License

MIT — see [LICENSE](LICENSE).

Made with :heart: by <a href="https://github.com/nkosi-tauro" target="_blank">Nkosilathi Tauro</a>