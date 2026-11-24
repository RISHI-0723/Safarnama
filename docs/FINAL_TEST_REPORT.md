# Final test report

Verification run on 24 November 2026. Baseline checkout
`6de8b403a1efd0efa89070b6488ceeb73aef26b8` had 28 backend, 43 automated ML
and 7 Chromium tests passing. The old unrestricted ML pytest collection also
tried to execute a Parquet diagnostic with missing data and dependencies. The
automated collection now targets `ml/tests`. The research diagnostic remains
available separately when its inputs exist.

| Check | Revised result |
|---|---|
| Backend pytest | 33 passed, one Starlette TestClient deprecation warning |
| Member 1 automated ML | 43 passed |
| Member 1 real export utility | Matched the original CSV value 82.6 and exercised missing route behavior |
| Vite production build | Passed, with existing React Router bundler warnings |
| Chromium | 8 passed against Chromium |
| Docker Compose config | Passed |
| Caddyfile validation | Passed using the existing Caddy container |
| Health and readiness | Both HTTP 200 with actual Delhi data. Empty database readiness returns 503 in tests. |
| Real GTFS and artifact validation | Matches archive and import digest, 20 mapped routes, 3,360 verified historical keys |
| Live integration | Disabled response and protobuf freshness/coordinate tests passed. Authorized upstream requests require a key. |
| Fresh Docker backend image | Blocked by workspace disk exhaustion during the VFS layer build. |

The app test server used the revised FastAPI files in the existing Python
container with the GTFS database mounted read-only. A local Vite production
preview served the rebuilt frontend. Browser fault paths intercept calls as
test fixtures. Successful journeys, map geometry and historical examples use
the real feed and historical artifact. The tests suppress external map tile
and font downloads to exercise map geometry independently of third-party
network access.

Use `scripts/run_tests` for Python, the frontend build and Compose validation.
Set `SAFARNAMA_TEST_ORIGIN` to include health probes and Chromium against a
server with the supplied feed. [Reproduce deployment and tests](DEPLOYMENT_GUIDE.md)

## End-to-end journey update, 24 November 2026

The source baseline at `d7ca5e1` passed 33 backend tests and 43 ML tests
before changes. It built successfully. A baseline Chromium run against the
legacy Compose HTTP endpoint passed six tests and failed two demand tests.
That endpoint served the older schedule build and lacked the current demand
routes. The revised end-to-end run used Caddy, the rebuilt frontend and
updated FastAPI inside an existing Docker container with the actual Delhi
database mounted read-only.

```sh
SAFARNAMA_PYTHON=/path/to/venv/bin/python scripts/run_tests
SAFARNAMA_TEST_ORIGIN=http://127.0.0.1:8967 SAFARNAMA_TEST_CHROMIUM=/usr/bin/chromium npm test
scripts/validate_data feeds/delhi_buses_static_gtfs_v1.zip --origin http://127.0.0.1:8967
docker compose config -q
```

Backend passed 37 tests, Member 1 passed all 43 automated ML tests and its
CSV comparison utility, and Vite built the frontend. The existing
Starlette TestClient and React Router warnings were visible in the output.
GTFS verification checked the import hash, SQLite integrity, calendar
relationships and actual route coverage. Both liveness and readiness
returned HTTP 200 through Caddy.

The clean image build remains unverified in this cloud workspace. A previous
build exhausted disk space and the remaining filesystem capacity was too low
to repeat it safely. The revised app was verified within the running
container harness using the existing persistent volume. Windows Docker
Desktop verification remains pending.

The app recovered readiness after a deliberate FastAPI process restart.
SQLite retained all 2,737,136 stop-time rows, and the read-only database's
size and SHA-256 were identical before and after the restart. The
verification did not restart the user's Docker Desktop installation.

The final Chromium suite passed all 14 tests with zero failures or skips.
It covered six widths from 360 to 1,440 pixels, the real transfer and
historical demand flows, and same-day departure filtering. An earlier
iteration exposed an ambiguous stop selector in the new test. The final
test selects two actual GTFS stops by their recorded stop codes.

## Hackathon submission verification

The documentation-only submission was checked against application commit
`4ffa20d`. The verification command used the prepared Python environment,
system Chromium and the local Caddy endpoint at port 8968:

```sh
SAFARNAMA_PYTHON=/path/to/venv/bin/python \
SAFARNAMA_TEST_ORIGIN=http://127.0.0.1:8968 \
SAFARNAMA_TEST_CHROMIUM=/usr/bin/chromium scripts/run_tests
```

37 backend tests, 43 ML tests and 14 Chromium tests passed. The real
prediction lookup utility, frontend production build, Compose configuration
and HTTP 200 liveness/readiness checks passed. Import behavior was covered
by temporary databases in the backend suite. The original feed ZIP passed
its member and recorded import checksum checks, and SQLite integrity, foreign
keys and table counts were verified on the existing read-only volume. A
full-size re-import and clean image build were not repeated in the
limited workspace.

All ten Mermaid blocks in the submission documentation were parsed and
rendered. The proposal and technical note were exported from Markdown to
Word and PDF. Both Word packages passed integrity and structure checks.
All four proposal pages and five technical-note pages were rasterized and
reviewed, including diagram, table and footer placement.
