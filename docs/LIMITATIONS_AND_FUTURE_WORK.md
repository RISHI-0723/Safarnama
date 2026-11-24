# Limitations and future work

| Evidence gap | Consequence for reviewers and users |
|---|---|
| The raw ETM dataset is accessed through its authorized distribution channel. | Runtime replay uses the published aggregate artifact. Full retraining requires authorized local data. |
| Stop matches use names, route constraints and stop order. | Coverage and name consistency do not establish geographic accuracy. |
| Vehicle and timestamp grouping produces candidate runs. | Ticket-derived segment loads need independent physical trip joins and validation. |
| Ticket issue and destination fields can differ from actual boarding and alighting. Passholders and unrecorded trips may be missing. | Ticket totals can understate or misplace passenger activity. |
| Vehicle capacities and actual passenger counts are unverified. | The prototype leaves occupancy percentages, seats, crowding bands and comfort ranking unavailable. |
| The demo covers 20 routes and uses zero-filled historical calendars. | Route-hour ticket demand applies only to supported keys. Missing reports or service changes can affect estimates. |
| Standard deviation is descriptive, and the model-selection window was reused. | No calibrated confidence or independent post-selection error claim is made. |
| Live positions need authorized credentials and an upstream check. | The default app is schedule-based. Coordinates alone cannot establish cabin occupancy. |

The next research milestone is to match independently confirmed stop
coordinates and physical trip identities, then validate segment loads against
observed counts and actual capacities. Route and hour accuracy should be
measured on unseen periods with known service coverage. Define crowding
categories and a comfort tradeoff only after calibration. For planner
operations, verify a new deployment with a clean image build, staging load
tests and the authorized feed. [Current project status](FINAL_PROJECT_STATUS.md)
