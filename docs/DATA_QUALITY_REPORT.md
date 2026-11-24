# Data quality report

Verified 24 November 2026 against the supplied Delhi static GTFS ZIP and the
recovered imported SQLite volume. Archive integrity passed for all 16 members
and its SHA-256 matched the recorded import.

```text
delhi_buses_static_gtfs_v1.zip
8eb05d9c21e7a6b42d7b49de45cb095b70ddee5b8f7716859330c9784c322f05
```

| Item | Verified database rows |
|---|---:|
| Stops | 6,862 |
| Routes | 2,574 |
| Trips | 80,357 |
| Stop times | 2,737,136 |
| Shape points | 965,607 |
| Weekly calendars | 1 |
| Calendar exception rows | 0 |

SQLite quick check returned `ok` and its foreign-key check returned zero
violations. The committed ingestion report recorded no orphan shape
references, invalid stop-time order, or trips with fewer than two stop calls.
Optional GTFS direction, block and distance fields are absent on many or all
records. Boarding and alighting times are scheduled. Route direction labels
for ML depend on the reviewed crosswalk and exact GTFS route codes. Consult the
import report when replacing the feed. [Recorded import](../backend/data/ingestion_report.json)

The backend validated 20 explicit directional mappings, 3,360 unique weekday
and hour buckets, and zero missing buckets within that export. The other
2,554 imported routes have no verified GTFS-to-export coverage. Calendar
weekdays use Monday = 0 through Sunday = 6 and hours 0–23, in Asia/Kolkata.
Zero estimates are preserved. Missing values are shown as unavailable. The
Git CSV digest and the manifest’s original CRLF digest are checked
independently by the validator. [Historical artifact and evaluation](ML_EVALUATION_REPORT.md)

```sh
scripts/validate_data feeds/delhi_buses_static_gtfs_v1.zip --origin http://127.0.0.1:8080
```

The public Delhi catalog can provide updated static releases. This report
identifies the supplied archive by checksum and records its own imported
contents. Vehicle positions use a separate authorized provider workflow.
[Delhi Open Transit Data documentation](https://otd.delhi.gov.in/documentation/)

The uploaded October ETM archive exceeded this executor’s 32 MiB transfer
limit. Its raw observations and the full-network export were not available
for verification in the checkout.

## Service calendar and transfer review

The active archive contains service ID `1` scheduled for all seven
weekdays from 2025-01-01 to 2040-01-01. SQLite returned zero unrecognized
trip service IDs and zero shape coordinates outside latitude/longitude
bounds. It has no calendar exceptions or explicit transfer rules. The
planner enforces the selected service date and handles GTFS times beyond
24:00 against the originating service day. This archive supplies no
validated walking distance or boarding guarantees.
[Journey planner validation](JOURNEY_PLANNER_VALIDATION.md)

## Original import details

The schedule milestone verified two `feed_info.txt` records. The imported
database recorded 18,457 departures at GTFS hour 24 or later and the
generated SQLite file was about 330 MB. Every supplied trip had a blank
`direction_id`. The archive and database are local inputs and outputs,
respectively. Use the recorded feed digest to reproduce the import.
[Historical test evidence](FINAL_TEST_REPORT.md#historical-verification-milestones)
