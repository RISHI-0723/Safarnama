# System architecture

SAFARNAMA uses static GTFS for journeys and a separate historical ticket-demand artifact for optional context. The raw ticket pipeline is offline. Its candidate-load experiments have no production data path.

```mermaid
flowchart LR
    GTFS["Authorized GTFS ZIP"] --> Import["GTFS importer"]
    Import --> DB["Neon PostgreSQL or local SQLite"]
    DB --> Planner["Journey, geometry and analytics services"]
    ETM["Authorized October ETM CSV"] --> Clean["Clean and aggregate"]
    Clean --> Demo["Versioned CSV, manifest and schema"]
    Demo --> Adapter["Verified directional adapter"]
    DB --> Adapter
    Planner --> API["FastAPI"]
    Adapter --> API
    Web["Vercel · React, Leaflet and Recharts"] -->|HTTPS| API
    Local["Local React application"] --> Caddy["Caddy same-origin proxy"]
    Caddy --> API
```

## Request and validation flow

```mermaid
flowchart TD
    User["Browser request"] --> Proxy["Hosted HTTPS request or local proxy"]
    Proxy --> Check["FastAPI inputs and request ID"]
    Check --> Query["Schedule and geometry query"]
    Check --> Artifact["Historical lookup"]
    Check --> Occupancy["Segment context and occupancy provider"]
    Query --> DB["Indexed PostgreSQL or SQLite"]
    Artifact --> Mapping{"Valid artifact and directional route?"}
    Mapping -->|Yes| Estimate["Route-hour value and metadata"]
    Mapping -->|No| Unavailable["Explicit unavailable reason"]
    Occupancy --> Nulls["Unavailable provider with null estimates"]
```

## Journey planning

```mermaid
flowchart TD
    Input["Stops, Delhi date, time and mode"] --> Clock["Resolve earliest boarding"]
    Clock --> Service["Resolve service calendars and exceptions"]
    Service --> Direct["Find indexed direct boardings"]
    Service --> Transfer["Find one-transfer paths"]
    Transfer --> Validate["Check stop rules, order and minimum wait"]
    Direct --> Unique["Deduplicate ordered route, stop and time keys"]
    Validate --> Unique
    Unique --> Rank["Rank by arrival or transfer penalty"]
    Rank --> Response["Timetable details and real trip geometry references"]
```

FastAPI uses SQLAlchemy and database indexes for stops, departure ranges and
ordered trip calls. Route geometry comes from stored GTFS shapes. Lower-cost
schedule requests and health checks are independent of the optional historical
artifact and live feed. [Deployment guide](DEPLOYMENT_GUIDE.md)

The React interface lazy-loads its Leaflet explorer and Recharts dashboard.
Expanded journey cards share identical route-day-hour demand lookups within
the itinerary and cancel them when details close or search inputs change.
The importer stages the SQLite replacement beside the current file and checks
relationships before replacing it. PostgreSQL imports validate within a
transaction before committing the feed. These boundaries keep timetable search
usable when an optional prediction source or external map layer is unavailable.
[Integration provenance](INTEGRATION_REPORT.md)
