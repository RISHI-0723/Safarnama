# Deployment guide

The tested deployment runs Caddy and FastAPI with Docker Compose. Caddy serves
the production Vite build, handles SPA paths and proxies the API on the same
origin. FastAPI uses SQLite on the persistent `transit` volume. One application
replica with a local volume is the supported starting point.

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

## Public HTTPS on a Docker host

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

The public deployment requires a public host, hostname and access to configure
its DNS and ports. No public target or DNS access was supplied.

## Feed updates and rollback

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

## Separate frontend and backend hosting

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

## Data verification and backups

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

Run `scripts/run_tests` for local automated verification. Hosted verification
remains unconfigured on the submission branch. Keep private feed download
credentials in an authorized local or deployment environment.

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
