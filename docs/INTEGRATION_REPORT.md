# Integration provenance

The initial full-stack archive contained the React planner, FastAPI
schedule backend, route explorer and schedule analytics. Its crowding
provider returned a general unavailable response. A separate frontend-only
snapshot used demo data and was outside the integrated runtime. The
supporting Member 1 archive supplied the `ml/` predictor, lookup, schema,
manifest, demo export, evaluation materials and tests.

The integration verified the archived Member 1 files against their source
snapshot. The source publication retained the ML implementation, its
automated tests and the validated runtime CSV, manifest, schema and examples.
A dozen exploratory generated CSVs were omitted, covering candidate-run
sensitivity, component diagnostics, matching statistics, route validation,
ticket exclusions and stop reviews. The raw ETM data, full-network export
and independently measured vehicle occupancy were unavailable.

During integration, comparison against the exported CSV confirmed the
historical route-hour results for all 20 mapped routes. A separate
trip-context check resolved the 717AUP route and ordered stops and returned
an unavailable crowding response with null load, confidence, category and
capacity. Detailed verification, older test counts and the later end-to-end
checks are recorded together in the final test report.

- [Historical demand integration and evaluation](ML_EVALUATION_REPORT.md)
- [Frontend and backend architecture](ARCHITECTURE.md)
- [API contract](API_CONTRACT.md)
- [Verification milestones](FINAL_TEST_REPORT.md#historical-verification-milestones)
- [Original Member 1 runtime handoff](../ml/outputs/SAFARNAMA_BACKEND_HANDOFF.md)
- [Original integration inventory and generated-file exclusions](https://github.com/RISHI-0723/Safarnama/blob/de8cca811ee33fb65f27b99052f5f67a108c2221/docs/INTEGRATION_REPORT.md)
