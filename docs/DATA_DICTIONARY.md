# Data dictionary

## Ticket input

| Field | Meaning and pipeline use |
|---|---|
| `passenger_count` | Number of people represented by a ticket. Must be a positive integer. Summed in historical demand. |
| `created_at` | Local ticket issue time supplied in IST. Provides the date, weekday and hourly bucket. |
| `route` | ETM route label. Trimmed and uppercased. Directional coverage uses a reviewed GTFS crosswalk. |
| `vehicle_number` | Vehicle identifier used for candidate-run research. Required by cleaning and kept out of published ticket-level outputs. |
| `start_stop_name`, `end_stop_name` | Ticket origin and destination labels. Boarding name is required by cleaning. Destination may be missing. |
| `amount`, `ticket_type_id`, `is_ac` | Provider fare amount, ticket class and AC indicator. They do not supply live fares, occupancy or capacity in the application. |

## Static GTFS

| File | Purpose and imported rows |
|---|---|
| `agency.txt` | Operator and local timezone · 2 |
| `stops.txt` | Stop IDs, names and coordinates · 6,862 |
| `routes.txt` | Route IDs, operator and labels · 2,574 |
| `trips.txt` | Run templates linked to route, service and optional shape · 80,357 |
| `stop_times.txt` | Ordered stop calls and service-relative times · 2,737,136 |
| `calendar.txt` | Recurring weekday flags and validity · 1 |
| `calendar_dates.txt` | Date-specific service additions and removals · absent |
| `shapes.txt` | Ordered map geometry coordinates · 965,607 |
| `transfers.txt` | Transfer rules and minimum times · absent |

## Historical demand artifact

The key is `route, day_of_week, hour`. Monday is 0 and Sunday is 6. Hour
uses Delhi civil time from 0 to 23. `predicted_passengers` is the historical
mean of summed ticket passenger counts across matching calendar dates.
`daily_std` is descriptive variability. `observed_days` may include
zero-filled dates. A missing prediction is unavailable. [API contract](API_CONTRACT.md)
