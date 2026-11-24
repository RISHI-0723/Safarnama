# Evaluation and results

## Static feed and historical exports

| Evidence | Result |
|---|---:|
| Imported GTFS stops / routes / trips | 6,862 / 2,574 / 80,357 |
| Imported stop times / shape points | 2,737,136 / 965,607 |
| Cleaned ticket rows / represented ticketed passengers | 1,317,730 / 1,422,016 |
| Deployed directional route coverage | 20 of 2,574, approximately 0.78% |
| Demo prediction rows / Git CSV bytes | 3,360 / 80,063 |
| Missing keys for the 20-route demo grid | 0 |

The static import and demo coverage were rechecked using the archive, original
volume and runtime API. ETM cleaning and matching totals come from Member 1's
preserved research evidence. The raw October file was not reprocessed for
this submission. [Import evidence](DATA_QUALITY_REPORT.md) · [Research reproducibility](../ml/REPRODUCIBILITY.md)

## Matching evaluation

| Measure | V2 | V3 |
|---|---:|---:|
| Cleaned ticket rows | 1,317,730 | 1,317,730 |
| Boarding coverage | 70.76% | 76.43% |
| Destination coverage | 69.94% | 76.16% |
| Both endpoints matched | 55.34% | 62.82% |
| GTFS-ordered ticket records | 728,657 | 826,960 |
| GTFS-ordered coverage | 55.30% | 62.76% |
| Records with an unmatched endpoint | 588,486 | 489,900 |
| Both matched but order invalid | 587 | 870 |

Coverage describes resolutions and ordered matches. It does not establish
geographic accuracy or physical trip assignment. [Machine-readable audit](../ml/outputs/matching_coverage_audit.json)

## Model selection

Training 1–24 October 2026. Model-selection window 25–31 October. Lower
values are better. WAPE divides total absolute error by total actual demand
across the evaluation slice.

| Top-20 route measure | Historical mean | CatBoost |
|---|---:|---:|
| MAE | 4.243 | 6.542 |
| RMSE | 6.900 | 11.290 |
| WAPE | 29.52% | 45.51% |

The same window selected the winning model and does not provide an untouched
test. The shipped mean was refit on 1–31 October. Full-network historical
mean WAPE reported in the research was 58.19%. [Model-selection report](../ml/outputs/ML_VALIDATION_REPORT.md)

## Software validation

The local verification run recorded 37 backend, 43 ML and 14 Chromium
tests passing. The frontend production
build, Compose configuration and API liveness/readiness checks passed.
The runtime browser verification reused the imported Delhi database in an
existing container. A clean container-image build remains unverified in this
workspace. The later hosted checks use the public Vercel and Render
endpoints. [Full test report](FINAL_TEST_REPORT.md) · [Hosted smoke checks](FINAL_TEST_REPORT.md#hosted-smoke-checks)
