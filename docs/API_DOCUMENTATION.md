# API guide for reviewers

Compose exposes the app at `http://127.0.0.1:8080`, FastAPI's interactive
reference at `/docs`, and the JSON OpenAPI document at `/openapi.json`.
The operating city timezone is Asia/Kolkata.

| Request | Response |
|---|---|
| `GET /health`, `GET /ready` | Process liveness and imported-timetable readiness |
| `GET /api/v1/stops`, `GET /api/v1/routes` | Searchable and paginated stop/route metadata |
| `GET /api/v1/journeys` | Direct and one-transfer alternatives, ordered leg references and timings |
| `GET /api/v1/routes/{route_id}/geometry` | Verified GTFS shape points or an unavailable status |
| `GET /api/v1/demand/historical` | Route-hour estimate or explicit unsupported/unavailable reason |
| `GET /api/v1/demand/profile`, `GET /api/v1/demand/coverage` | Route-day profile and artifact coverage |
| `GET /api/v1/crowding` | Segment context and an unavailable response when evidence is insufficient |
| `GET /api/v1/analytics` | Timetable counts, service dates, hourly starts and common links |
| `GET /api/v1/live/vehicles` | Authorized provider status and positions when available. Disabled by default. |

```sh
curl -fsS 'http://127.0.0.1:8080/api/v1/journeys?origin=2640&destination=3250&date=2026-11-27&time=08:35&mode=historical'
curl -fsS 'http://127.0.0.1:8080/api/v1/demand/historical?route_id=2171&date=2026-11-27&time=08:35'
curl -fsS 'http://127.0.0.1:8080/api/v1/demand/coverage?limit=1'
```

The historical lookup example returns 82.6 estimated ticketed passengers
per route-hour for 717AUP. The planner defaults to upcoming searches and
uses the current Delhi clock for same-day requests. Use historical mode
for an explicitly past timetable. [Complete field contract](API_CONTRACT.md)
