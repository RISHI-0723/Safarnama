# Deployment guide

## Hosted production

The public deployment has separate frontend and API origins. The frontend
runs on Vercel, the FastAPI backend runs on Render, and the hosted timetable
uses Neon PostgreSQL. The Compose instructions later in this guide use a
local SQLite database.

- [Vercel application](https://safarnama-eosin.vercel.app/)
- [Render API origin](https://safarnama-api-s6zs.onrender.com/) · [OpenAPI UI](https://safarnama-api-s6zs.onrender.com/docs)
- [API readiness](https://safarnama-api-s6zs.onrender.com/ready)
- [Source repository](https://github.com/RISHI-0723/Safarnama)

### Vercel frontend

For a fresh deployment, import the GitHub repository into Vercel and select
`main` as the production branch. Use these settings with the repository's
Vite configuration:

| Setting | Value |
|---|---|
| Root directory | Repository root |
| Framework preset | Vite |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Frontend build variable | `VITE_API_BASE_URL=https://safarnama-api-s6zs.onrender.com/api/v1` |

Vite injects this value when it builds the frontend. It is publicly visible
in the bundle. Use the versioned prefix rather than an individual endpoint.
The current interface uses hash-based navigation. [Vercel Vite guide](https://vercel.com/docs/frameworks/frontend/vite)

### Render backend and Neon

Connect the same GitHub repository and production branch to a Render Docker
web service. Set the Dockerfile path to `backend/Dockerfile` and keep the
build context at the repository root. The image needs access to both
`backend/` and the packaged `ml/` files.

The Dockerfile starts Uvicorn on `0.0.0.0:8000`. Use the image command and
ensure Render routes traffic to that listener. For a fresh service, set
`PORT=8000` to match the image listener. If a service explicitly
overrides its start command, bind Uvicorn to the assigned `$PORT` instead
and keep the service port consistent. [Render web services](https://render.com/docs/web-services)

| Render variable | Purpose |
|---|---|
| `SAFARNAMA_DATABASE_URL` | Private Neon PostgreSQL connection string. Keep the TLS options in the URL provided by Neon. |
| `SAFARNAMA_CORS_ORIGINS` | Exact comma-separated trusted origins. Include `https://safarnama-eosin.vercel.app` without a trailing slash. |

Use a hosted PostgreSQL connection for Render. Local development can use the
default SQLite file. Keep the database string in the backend environment.
[Neon and GTFS import](#postgresql-and-neon-data-operations)

### Health checks and production verification

| Endpoint | What it checks |
|---|---|
| `/health` | Process liveness after startup. It performs no database query. |
| `/api/v1/health` | Connectivity to the configured database. |
| `/ready` | Database access and the presence of stops, trips, stop times, and either a recurring service calendar or a date that adds service. |

Set Render's health check path to `/health` when bootstrapping a service
with an empty feed. Wait for `/ready` before treating that service as ready
for commuter traffic. With a loaded database, `/ready` can serve as the
stricter Render probe. [Render health-check settings](https://render.com/docs/health-checks)

```bash
api=https://safarnama-api-s6zs.onrender.com
curl -fsS --max-time 90 "$api/health"
curl -fsS --max-time 90 "$api/api/v1/health"
curl -fsS --max-time 90 "$api/ready"
curl -fsS --max-time 90 "$api/api/v1/demand/coverage?limit=1"
curl -fsS --max-time 90 -D - -o /dev/null \
  -H 'Origin: https://safarnama-eosin.vercel.app' "$api/api/v1/stops?limit=1"
```

A ready response is HTTP 200 with `database: ok` and `schedules: ready`.
The stop request should allow the Vercel origin in the CORS response header.
Verify stop selection and a journey on the public website, and compare
`/api/v1/analytics` with the completed import report.
[Hosted smoke-check evidence](FINAL_TEST_REPORT.md#hosted-smoke-checks)

### Troubleshooting the hosted service

| Symptom | What to check |
|---|---|
| A first request takes longer than later requests | Render Free can spin down after 15 minutes without inbound traffic. Allow a cold start and retry the health and readiness probes before checking the UI again. |
| `/health` succeeds but `/ready` returns `database: ok, schedules: missing` | Verify the Render database setting and that the intended Neon database contains the imported feed. The SQLite fallback may also produce this response if the hosted variable is absent. |
| `/api/v1/health` returns 503 or startup fails | Check the private connection setting, credentials, TLS options, and PostgreSQL availability. |
| `/ready` returns `database: unavailable, schedules: unknown` | Check connectivity, table availability and query permissions in the intended database. |
| Website loads but stop search fails | Check the deployed frontend API prefix, Render readiness and the exact configured frontend origin. |

[Render Free service behavior](https://render.com/docs/free)

## Local or staging

1. Install Docker Engine with Compose v2. Use a machine with at least 1 GB of
   free space for the feed, the active database and a staged replacement, plus
   free space for container images and logs.
2. Copy `.env.example` to `.env`. Create `feeds/` and copy in the Delhi GTFS ZIP. The directory and file
   must be readable by container UID 10001.
3. Run these commands from the repository root.

   ```sh
   docker compose build
   docker compose run --rm backend python -m scripts.import_gtfs \
     /feeds/delhi_buses_static_gtfs_v1.zip --database /data/safarnama.db \
     --report /data/ingestion_report.json
   docker compose up -d --wait
   curl -fsS http://127.0.0.1:8080/api/v1/ready
   ```

4. Open the planner and test the direct and transfer examples in the README.
   Open both journeys on the map and check the analytics dashboard.

On CI networks with a custom certificate authority, Compose can supply the CA
bundle as a BuildKit build secret named `build_ca` to both image builds. The
registry and dependency downloads still use TLS verification. Tested in this
workspace with a local override containing:

```yaml
services:
  backend:
    build:
      secrets: [build_ca]
  frontend:
    build:
      secrets: [build_ca]
secrets:
  build_ca:
    file: /etc/ssl/certs/ca-certificates.crt
```

## Alternative self-hosted HTTPS with Compose

1. Point a DNS A/AAAA record for the chosen hostname at the Docker host and
   allow inbound TCP 80 and 443. Keep backend port 8000 internal.
2. Set the following in `.env` before `docker compose up -d --wait`.

   ```dotenv
   SAFARNAMA_SITE_ADDRESS=safarnama.example.org
   SAFARNAMA_HTTP_BIND=0.0.0.0:80
   SAFARNAMA_HTTPS_BIND=0.0.0.0:443
   SAFARNAMA_CORS_ORIGINS=
   SAFARNAMA_LOG_LEVEL=INFO
   ```

3. Check TLS and readiness with
   `curl -fsS https://safarnama.example.org/api/v1/ready`. Check browser developer
   tools for failed same-origin requests, then run
   `SAFARNAMA_TEST_ORIGIN=https://safarnama.example.org npm test`.
4. Inspect service logs with `docker compose logs --tail=100 backend frontend`.
   Preserve both the transit data and Caddy certificate volumes.

## Local SQLite feed updates and rollback

Keep the source feed outside Git. Back up the existing database and ingestion
report before replacing either. Stop the backend before a feed update because
workers cache schedule analytics and pooled connections can retain the old
file. Repeat the import command with the new filename, inspect the new report,
then start the stack again with `docker compose up -d --wait`. The importer
builds a new database beside the old one and swaps it in after consistency
checks. A failed post-parse import leaves the prior database in place and
writes `ingestion_report.failed.json` when a report path is configured. To roll
back, stop the backend, restore the prior database and matching report to the
same volume and start the stack. Avoid `docker compose down -v` unless deleting
the data and certificates is intended. Do not run multiple imports against
the same volume concurrently.

## Alternative standalone frontend and backend

- Build the static frontend using `npm ci && npm run build` and serve `dist/`.
  For a separate API origin, set `VITE_API_BASE_URL=https://api.example.org/api/v1`
  **before** building. For same-origin hosting, forward `/api/v1/*` to FastAPI.
  Serve `index.html` for app paths and use HTTPS for both origins.
- Start the backend in `backend/` with
  `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`. Install
  `backend/requirements.txt`, use a persistent writable directory and set
  `SAFARNAMA_DATABASE_URL=sqlite:////absolute/path/safarnama.db`.
  Give the import command the same absolute path with `--database`.
- Set `SAFARNAMA_CORS_ORIGINS` to exact comma-separated frontend origins such
  as `https://planner.example.org`. `SAFARNAMA_LOG_LEVEL` defaults to `INFO`.
  Use `/api/v1/ready` for traffic readiness and `/api/v1/health` for connection
  checks. Initial analytics generation takes several seconds on the Delhi feed.
- `SAFARNAMA_BACKEND_ORIGIN` is the Vite proxy target in local dev or preview.
  `VITE_STOPS_PATH`, `VITE_JOURNEYS_PATH`, `VITE_ROUTES_PATH`,
  `VITE_ANALYTICS_PATH` and `VITE_CROWDING_PATH` default to their matching
  versioned endpoint suffixes. Vite values are publicly readable.


## Historical demand in deployment

The backend image includes the two Member 1 lookup modules, demo CSV,
manifest, response schema and the explicitly validated application route
crosswalk. Compose defaults to `/app/ml/outputs` inside the container.
For a custom export, mount the artifact directory read-only and set
`SAFARNAMA_ML_ARTIFACT_DIR` to its in-container path. An empty variable
disables historical demand. A different GTFS route catalog needs its own
verified directional mapping before deployment.

The frontend uses `VITE_HISTORICAL_DEMAND_PATH`, relative to
`VITE_API_BASE_URL`, with default `/demand/historical`. FastAPI exposes it
under `/api/v1`. Check readiness and the example lookup after changing
backend URLs, feeds, or artifacts. No original ETM data or credentials
are required for the shipped demo export.

## Feed verification and backups

Run `scripts/validate_data feeds/delhi_buses_static_gtfs_v1.zip --origin http://127.0.0.1:8080`
to verify ZIP integrity, the archive checksum and historical coverage on the
running app. The initial local import command `scripts/import_gtfs` refuses an
existing database or generated report. Keep deployment backups off the Docker
host. For a consistent online SQLite backup, use SQLite's `.backup` command
and validate the destination using `PRAGMA quick_check;`. Record the
matching GTFS archive hash, ingestion report, application revision and
configuration, and test restoration using a separate volume.

For standalone hosting, install
`python -m pip install -c backend/constraints.txt -r backend/requirements-runtime.txt`
from the repository root and start with `scripts/run_backend` or Uvicorn's
`--no-access-log` flag. Protect process logs and monitor `/health` and `/ready`.
Use a read-only mount for a custom ML crosswalk and set
`SAFARNAMA_ML_ROUTE_MAPPING` to the mapped path. Custom export manifests use
`coverage_scope: full_network` and declare the CSV filename, row count,
route count and SHA-256. The service exposes the subset with unambiguous
reviewed GTFS mappings. The original demo still requires a mapping for every
demo route.

## Delhi vehicle feed

Request access and review the provider's redistribution terms before enabling
the service. Set `SAFARNAMA_LIVE_ENABLED=true` and inject
`SAFARNAMA_DELHI_LIVE_KEY` through a protected runtime secret. Leave the
feature off until the account is authorized for the intended use. Verify fresh
vehicle responses from `/api/v1/live/vehicles` without printing the key or
query URL. The feed contains positions. It supplies no verified passenger
occupancy for the app. [Apply for Delhi live access](https://otd.delhi.gov.in/data/realtime/)

Run `scripts/run_tests` for local automated verification. Use the public
probes above for hosted verification. Store private feed download credentials
in an authorized local or deployment environment.

## Update an existing Windows Docker Desktop installation

Run `docker compose ls` and record the current project name. Keep the
existing `.env`, feed archive and database volume. To apply updated source
from a Git clone, pull the new source, then run from the repository root in
PowerShell:

```powershell
docker compose up -d --build --wait
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/ready
```

If replacing an extracted GitHub ZIP in a new directory, copy the local
configuration and feed, then pass the same Compose project name with
`docker compose -p YOUR_EXISTING_PROJECT up -d --build --wait`. This keeps
the existing database volume attached. Normal rebuilds and restarts reuse
the imported data. Run the import only for first setup or an intentional
feed refresh.

## PostgreSQL and Neon data operations

Local development and the default Compose service use SQLite. A separately
hosted backend can use Neon by setting `SAFARNAMA_DATABASE_URL` in its
private environment. Use the connection string from Neon and preserve its
TLS parameters. Either a plain `postgresql://` or an explicit
`postgresql+psycopg://` URL selects Psycopg 3. The following value is a
placeholder.

```dotenv
SAFARNAMA_DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

Set the URL in Render's private service settings at rollout. Keep the frontend
pointing at the intended API and configure the hosted backend's CORS origins
if they are served separately. The Python server creates missing tables
at startup. The importing role needs permission to create tables and
insert rows. For a feed refresh, it also needs permission to truncate the
existing GTFS tables. The packaged historical demand artifact stays on
disk in the backend image.

### Initial GTFS import for a fresh hosted database

The current hosted feed has been loaded. For a new empty database, use a
dedicated database or staging branch and a direct Neon connection. Export
its URL privately in `SAFARNAMA_DATABASE_URL`. With the backend dependencies
installed, run from `backend/` on a trusted machine that holds the authorized
GTFS archive:

```sh
python -m scripts.import_gtfs ../feeds/delhi_buses_static_gtfs_v1.zip \
  --postgres --report /path/to/neon-gtfs-import.json
```

The explicit `--postgres` flag selects the database in the environment.
Without that flag the CLI retains its local SQLite file behavior.
PostgreSQL imports use bounded batches and commit after validation.
An existing feed requires explicit `--replace`. The refresh holds
exclusive locks on the GTFS tables, so stop traffic and restart the app
afterwards to refresh its cached timetable and route mapping. A failed
replacement rolls back and retains the prior feed. Check `/ready` after
the import, then compare key route counts with the report.

### Verify on a disposable PostgreSQL instance

Set `SAFARNAMA_TEST_POSTGRES_URL` to a database on a local Unix socket or
loopback address, then run `python -m pytest -q` from `backend/`.
The PostgreSQL integration tests create separate temporary schemas. They
cover startup, empty and loaded readiness, rollback, schedule and route
queries, and import reporting. Use a disposable local database for these
tests. The runtime can use Neon's pooled endpoint, with client-side
automatic prepared statements disabled. Direct endpoint imports are
separate from serving HTTP traffic. Confirm storage and compute use in Neon
before rollout. [Neon Free plan limits](https://neon.com/blog/neon-free-plan-1-gb-per-project)

### Compatibility and verification

The SQLite file importer uses a staged database, foreign-key PRAGMA and
SQLite parameter binding. Those operations stay confined to SQLite.
PostgreSQL creates the same schema, loads bounded batches with typed array
parameters, and counts inserted rows explicitly while retaining duplicate
reporting. Route queries preserve the existing response field names,
case-insensitive search and null ordering across both engines. GTFS
identifiers, ISO service dates and seconds since service midnight retain
their existing representation.

On 24 November 2026, the supplied Delhi GTFS archive was imported from
scratch into isolated PostgreSQL 17.5 and SQLite databases. Both reports
matched the committed import report. PostgreSQL contained 6,862 stops,
2,574 routes, 80,357 trips, 2,737,136 stop times and 965,607 shape points.
The database occupied 624,258,195 bytes (595.34 MiB), including indexes.
Readiness, routes, geometry, journey search, analytics and historical demand
were exercised on the full PostgreSQL feed. This measurement is below the
published 1 GB free-plan storage limit. Neon meters its own project usage.
The live analytics and readiness probes separately confirm the hosted
timetable is available. [Hosted verification](FINAL_TEST_REPORT.md#hosted-smoke-checks)
