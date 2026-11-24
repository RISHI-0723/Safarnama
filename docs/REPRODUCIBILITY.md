# Reproducibility guide

## Start from the integrated repository

Use Python 3.12, Node 22.12 or later, Docker with Compose v2, and Bash for
the shell wrappers. Install Chromium with `npx playwright install chromium`.
Clone or extract the primary repository, place the authorized archive at
`feeds/delhi_buses_static_gtfs_v1.zip`, then run:

```sh
scripts/setup
scripts/validate_data feeds/delhi_buses_static_gtfs_v1.zip
scripts/import_gtfs feeds/delhi_buses_static_gtfs_v1.zip
scripts/run_backend --port 8000
```

In a second terminal, run `scripts/run_frontend`. The import wrapper
refuses an existing local database. For Compose installation or to preserve
an existing named volume during a Windows Docker Desktop update, follow the
deployment steps. [Deployment guide](DEPLOYMENT_GUIDE.md)

The default frontend API prefix is `/api/v1`. Set
`SAFARNAMA_BACKEND_ORIGIN` for a different Vite backend port,
`SAFARNAMA_DATABASE_URL` for a custom SQLite location,
`SAFARNAMA_ML_ARTIFACT_DIR` for a mounted artifact directory and
`SAFARNAMA_ML_ROUTE_MAPPING` for a reviewed replacement crosswalk.
Separate origins may require `SAFARNAMA_CORS_ORIGINS`. Compose
defaults to loopback for local review. The optional live feed requires
`SAFARNAMA_LIVE_ENABLED` and an authorized server-side key.
Keep all credentials out of source control. [Environment example](../.env.example)

```sh
SAFARNAMA_TEST_ORIGIN=http://127.0.0.1:5173 scripts/run_tests
scripts/validate_data feeds/delhi_buses_static_gtfs_v1.zip --origin http://127.0.0.1:5173
(cd ml && ../backend/.venv/bin/python src/safarnama_predictor.py --route 717AUP --datetime "2026-11-27T08:00:00+05:30")
```

Expected artifact response for the example is 82.6 historical ticketed
passengers per route-hour. Python backend and ML tests, Vite build and
Compose configuration run even when no browser origin is specified.

## Full research workflow with authorized data

Open the `ml/` directory in a separate development environment and install
`requirements.txt`. Place the authorized October ETM CSV and extracted GTFS
members in the documented `data/raw/` paths. Clean ETM, build route stops,
run V1/V2 matching and order validation, then V3 component recovery, order
check and comparison. Candidate-run experiments consume the V2 ordered
inputs. Route-hour demand branches from the cleaned tickets. It runs
`build_hourly_demand.py`, `evaluate_hourly_demand.py`, `export_predictions.py`,
then `prepare_backend_handoff.py`. The full `generate_final_handoff.py`
also requires local generated reports, which the ML guide enumerates.
The integrated artifact and verified demo are available independently of
the raw dataset. [Detailed research commands](../ml/REPRODUCIBILITY.md)
