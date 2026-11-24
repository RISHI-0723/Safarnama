"""Validate and import static GTFS into SQLite or PostgreSQL."""

import csv
import io
import json
import os
import sqlite3
import tempfile
import zipfile
from collections import Counter
from contextlib import closing, contextmanager
from datetime import datetime
from hashlib import file_digest
from pathlib import Path

from sqlalchemy import URL, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.database import initialize_database, make_engine, normalize_database_url


TABLES = {
    "agency.txt": ("agencies", ("agency_id", "agency_name", "agency_timezone")),
    "stops.txt": ("stops", ("stop_id", "stop_name", "stop_lat", "stop_lon")),
    "routes.txt": ("routes", ("route_id", "agency_id", "route_type")),
    "calendar.txt": ("calendars", ("service_id", "start_date", "end_date")),
    "calendar_dates.txt": ("calendar_dates", ("service_id", "date", "exception_type")),
    "trips.txt": ("trips", ("trip_id", "route_id", "service_id")),
    "stop_times.txt": ("stop_times", ("trip_id", "stop_id", "stop_sequence")),
    "shapes.txt": ("shape_points", ("shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence")),
    "transfers.txt": ("transfers", ("from_stop_id", "to_stop_id", "transfer_type")),
}
REQUIRED = set(TABLES) - {"calendar.txt", "calendar_dates.txt", "shapes.txt", "transfers.txt"}
ORDER = list(TABLES)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
INSERT = {
    "agency.txt": "INSERT INTO agencies VALUES (?,?,?)",
    "stops.txt": "INSERT INTO stops (id,code,name,lat,lng) VALUES (?,?,?,?,?)",
    "routes.txt": "INSERT INTO routes (id,agency_id,short_name,long_name,description,route_type) VALUES (?,?,?,?,?,?)",
    "calendar.txt": "INSERT INTO calendars VALUES (?,?,?,?,?,?,?,?,?,?)",
    "calendar_dates.txt": "INSERT INTO calendar_dates VALUES (?,?,?)",
    "trips.txt": "INSERT INTO trips (id,route_id,service_id,headsign,direction_id,shape_id) VALUES (?,?,?,?,?,?)",
    "stop_times.txt": "INSERT INTO stop_times (trip_id,stop_sequence,stop_id,arrival,departure) VALUES (?,?,?,?,?)",
    "shapes.txt": "INSERT INTO shape_points VALUES (?,?,?,?)",
    "transfers.txt": "INSERT INTO transfers VALUES (?,?,?,?)",
}

KEY_TABLES = {"agency.txt", "stops.txt", "routes.txt", "calendar.txt", "trips.txt"}
BATCH_SIZE = 5000


@contextmanager
def _sqlite_import(database_path):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="gtfs-", suffix=".db", dir=database_path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        engine = make_engine(URL.create("sqlite", database=str(temp_path)))
        try:
            Base.metadata.create_all(engine)
        finally:
            engine.dispose()
        with closing(sqlite3.connect(temp_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        temp_path.replace(database_path)
    finally:
        temp_path.unlink(missing_ok=True)


@contextmanager
def _postgres_import(database_url, replace):
    engine = make_engine(database_url)
    try:
        with engine.begin() as connection:
            initialize_database(connection)
            tables = [Base.metadata.tables[TABLES[name][0]] for name in ORDER]
            # The names are fixed by our own models, never supplied by the feed.
            table_names = ", ".join(table.name for table in tables)
            connection.exec_driver_sql(f"LOCK TABLE {table_names} IN ACCESS EXCLUSIVE MODE")
            if any(connection.execute(select(1).select_from(table).limit(1)).first() for table in tables):
                if not replace:
                    raise ValueError("PostgreSQL already contains GTFS rows; use --replace to refresh the feed")
                connection.exec_driver_sql(f"TRUNCATE TABLE {table_names}")
            yield connection
    finally:
        engine.dispose()


def _sqlite_batch(connection, name, batch, stats):
    for values in batch:
        try:
            connection.execute(INSERT[name], values)
            stats["imported"] += 1
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint failed" in str(error):
                stats["duplicates"] += 1
            else:
                stats["rejected"] += 1
                stats["validation_errors"][str(error)] += 1


def _postgres_batch(connection, name, batch, stats):
    table = Base.metadata.tables[TABLES[name][0]]
    quote = connection.dialect.identifier_preparer.quote
    columns = ", ".join(quote(column.name) for column in table.columns)
    key = ", ".join(quote(column.name) for column in table.primary_key.columns)
    arguments = ", ".join(
        f"CAST(%s AS {column.type.compile(dialect=connection.dialect)}[])"
        for column in table.columns
    )
    # One array bind per column keeps every batch small on the wire and
    # returns an accurate inserted count without fetching individual rows.
    inserted = connection.exec_driver_sql(f"""
        WITH written AS (
            INSERT INTO {quote(table.name)} ({columns})
            SELECT * FROM unnest({arguments})
            ON CONFLICT ({key}) DO NOTHING
            RETURNING 1
        )
        SELECT count(*) FROM written
    """, tuple(list(values) for values in zip(*batch))).scalar_one()
    stats["imported"] += inserted
    stats["duplicates"] += len(batch) - inserted


def _validate_postgres_values(values):
    for value in values:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("text field contains a NUL character")
        if isinstance(value, int) and not -(2**31) <= value < 2**31:
            raise ValueError("integer field outside PostgreSQL integer range")


def gtfs_time(value: str) -> int | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("invalid GTFS time")
    hour, minute, second = map(int, parts)
    if hour > 99 or minute >= 60 or second >= 60:
        raise ValueError("invalid GTFS time")
    return hour * 3600 + minute * 60 + second


def gtfs_date(value: str) -> str:
    return datetime.strptime(value, "%Y%m%d").date().isoformat()


def _point(lat: str, lng: str) -> tuple[float, float]:
    latitude, longitude = float(lat), float(lng)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid coordinates")
    return latitude, longitude


def _values(name: str, row: dict[str, str], ids: dict[str, set[str]]) -> tuple:
    def need(field):
        value = row.get(field, "").strip()
        if not value:
            raise ValueError(f"missing {field}")
        return value

    if name == "agency.txt":
        timezone = need("agency_timezone")
        if timezone not in {"Asia/Kolkata", "Asia/Calcutta"}:
            raise ValueError("Delhi feeds must use Asia/Kolkata")
        return need("agency_id"), need("agency_name"), timezone
    if name == "stops.txt":
        return need("stop_id"), row.get("stop_code") or None, need("stop_name"), *_point(need("stop_lat"), need("stop_lon"))
    if name == "routes.txt":
        agency = need("agency_id")
        if agency not in ids["agency.txt"]:
            raise ValueError("unknown agency_id")
        return need("route_id"), agency, row.get("route_short_name") or None, row.get("route_long_name") or None, row.get("route_desc") or None, int(need("route_type"))
    if name == "calendar.txt":
        start, end = gtfs_date(need("start_date")), gtfs_date(need("end_date"))
        if start > end:
            raise ValueError("service date range reversed")
        days = tuple(int(need(day)) for day in WEEKDAYS)
        if any(day not in (0, 1) for day in days):
            raise ValueError("invalid weekday flag")
        return need("service_id"), *days, start, end
    if name == "calendar_dates.txt":
        kind = int(need("exception_type"))
        if kind not in (1, 2):
            raise ValueError("invalid calendar exception")
        return need("service_id"), gtfs_date(need("date")), kind
    if name == "trips.txt":
        route, service = need("route_id"), need("service_id")
        if route not in ids["routes.txt"]:
            raise ValueError("unknown route_id")
        if service not in ids["calendar.txt"] and service not in ids["calendar_dates.txt"]:
            raise ValueError("unknown service_id")
        return need("trip_id"), route, service, row.get("trip_headsign") or None, row.get("direction_id") or None, row.get("shape_id") or None
    if name == "stop_times.txt":
        trip, stop = need("trip_id"), need("stop_id")
        if trip not in ids["trips.txt"] or stop not in ids["stops.txt"]:
            raise ValueError("unknown trip_id or stop_id")
        sequence = int(need("stop_sequence"))
        if sequence < 0:
            raise ValueError("negative stop_sequence")
        arrival, departure = gtfs_time(row.get("arrival_time", "")), gtfs_time(row.get("departure_time", ""))
        if arrival is None and departure is None:
            raise ValueError("missing arrival and departure")
        if arrival is not None and departure is not None and departure < arrival:
            raise ValueError("departure before arrival")
        return trip, sequence, stop, arrival, departure
    if name == "shapes.txt":
        sequence = int(need("shape_pt_sequence"))
        if sequence < 0:
            raise ValueError("negative shape_pt_sequence")
        return need("shape_id"), sequence, *_point(need("shape_pt_lat"), need("shape_pt_lon"))
    if name == "transfers.txt":
        start, end = need("from_stop_id"), need("to_stop_id")
        kind = int(need("transfer_type"))
        if kind not in (0, 1, 2, 3) or any(
            row.get(field) for field in ("from_route_id", "to_route_id", "from_trip_id", "to_trip_id")
        ):
            raise RuntimeError("unsupported route-specific, trip-specific or in-seat transfer")
        if start not in ids["stops.txt"] or end not in ids["stops.txt"]:
            raise ValueError("unknown transfer stop")
        minimum = int(row["min_transfer_time"]) if row.get("min_transfer_time") else None
        if (kind == 2 and minimum is None) or (minimum is not None and minimum < 0):
            raise ValueError("invalid min_transfer_time")
        return start, end, kind, minimum
    raise ValueError("unexpected GTFS table")


def import_gtfs(
    zip_path: Path, database_path: Path | None = None, report_path: Path | None = None,
    *, database_url: str | URL | None = None, replace: bool = False,
) -> dict:
    """Replace a SQLite file or load PostgreSQL in a rollback-safe transaction."""
    if (database_path is None) == (database_url is None):
        raise ValueError("Select exactly one GTFS database target")
    postgres = database_url is not None
    if postgres and normalize_database_url(database_url).get_backend_name() != "postgresql":
        raise ValueError("GTFS database_url must be a PostgreSQL URL")
    with zip_path.open("rb") as feed_file:
        digest = file_digest(feed_file, "sha256").hexdigest()
    report = {"source": zip_path.name, "sha256": digest, "tables": {}, "errors": []}
    with zipfile.ZipFile(zip_path) as archive:
        relevant = [item.filename for item in archive.infolist() if item.filename in TABLES or item.filename == "feed_info.txt"]
        duplicates_in_zip = [name for name, count in Counter(relevant).items() if count > 1]
        if duplicates_in_zip:
            raise ValueError(f"Duplicate GTFS files in ZIP: {', '.join(sorted(duplicates_in_zip))}")
        names = {name for name in archive.namelist() if name in TABLES}
        missing = sorted(REQUIRED - names)
        if missing:
            raise ValueError(f"Missing required GTFS files: {', '.join(missing)}")
        if not ({"calendar.txt", "calendar_dates.txt"} & names):
            raise ValueError("Missing calendar.txt and calendar_dates.txt")
        for name in names:
            with archive.open(name) as raw:
                reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
                header = next(reader, [])
            absent = sorted(set(TABLES[name][1]) - set(header))
            if absent:
                raise ValueError(f"{name}: missing columns {', '.join(absent)}")
        if "feed_info.txt" in archive.namelist():
            feed = {"available": True, "total": 0, "validated": 0, "rejected": 0, "validation_errors": Counter()}
            with archive.open("feed_info.txt") as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
                required = {"feed_publisher_name", "feed_publisher_url", "feed_lang"}
                absent = required - set(reader.fieldnames or [])
                if absent:
                    raise ValueError(f"feed_info.txt: missing columns {', '.join(sorted(absent))}")
                for row in reader:
                    feed["total"] += 1
                    try:
                        if not all(row.get(key) for key in required):
                            raise ValueError("missing publisher name, URL, or language")
                        start = gtfs_date(row["feed_start_date"]) if row.get("feed_start_date") else None
                        end = gtfs_date(row["feed_end_date"]) if row.get("feed_end_date") else None
                        if start and end and start > end:
                            raise ValueError("feed date range reversed")
                        feed["validated"] += 1
                    except (ValueError, KeyError) as error:
                        feed["rejected"] += 1
                        feed["validation_errors"][str(error)] += 1
            feed["validation_errors"] = dict(feed["validation_errors"])
            report["feed_info"] = feed
        else:
            report["feed_info"] = {"available": False, "total": 0, "validated": 0, "rejected": 0, "validation_errors": {}}
        target = _postgres_import(database_url, replace) if postgres else _sqlite_import(database_path)
        write_batch = _postgres_batch if postgres else _sqlite_batch
        try:
            with target as connection:
                query = connection.exec_driver_sql if postgres else connection.execute
                ids = {name: set() for name in TABLES}
                for name in ORDER:
                    if name not in names:
                        report["tables"][name] = {"available": False, "total": 0, "imported": 0, "rejected": 0, "duplicates": 0, "missing_values": {}}
                        continue
                    stats = {"available": True, "total": 0, "imported": 0, "rejected": 0, "skipped": 0, "duplicates": 0, "missing_values": Counter(), "validation_errors": Counter()}
                    batch = []
                    def flush():
                        if not batch:
                            return
                        write_batch(connection, name, batch, stats)
                        batch.clear()
                    with archive.open(name) as raw:
                        for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")):
                            stats["total"] += 1
                            for field, value in row.items():
                                if not value:
                                    stats["missing_values"][field] += 1
                            try:
                                values = _values(name, row, ids)
                                if postgres:
                                    _validate_postgres_values(values)
                                if name in KEY_TABLES:
                                    key = values[0]
                                    if key in ids[name]:
                                        stats["duplicates"] += 1
                                        continue
                                    ids[name].add(key)
                                if name == "calendar_dates.txt":
                                    ids[name].add(values[0])
                                batch.append(values)
                                if len(batch) >= BATCH_SIZE:
                                    flush()
                            except (ValueError, KeyError, TypeError) as error:
                                stats["rejected"] += 1
                                stats["validation_errors"][str(error)] += 1
                    flush()
                    stats["missing_values"] = dict(stats["missing_values"])
                    stats["validation_errors"] = dict(stats["validation_errors"])
                    report["tables"][name] = stats
                bad_order = query("""SELECT COUNT(*) FROM (
                    SELECT trip_id, stop_sequence, arrival, departure,
                           MAX(COALESCE(departure, arrival)) OVER (
                               PARTITION BY trip_id ORDER BY stop_sequence
                               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                           ) AS previous_departure
                    FROM stop_times
                ) AS sequenced WHERE COALESCE(arrival, departure) < previous_departure""").fetchone()[0]
                report["consistency"] = {"out_of_order_stop_times": bad_order}
                for required in ("agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"):
                    if report["tables"][required]["imported"] < 1:
                        raise ValueError(f"{required}: no valid records; existing database preserved")
                report["consistency"]["trips_without_two_stop_times"] = query("""
                    SELECT COUNT(*) FROM trips
                    WHERE (SELECT COUNT(*) FROM stop_times WHERE trip_id=trips.id) < 2
                """).fetchone()[0]
                if bad_order:
                    raise ValueError(f"{bad_order} stop times run backward within a trip; existing database preserved")
                missing_shapes = query("SELECT COUNT(*) FROM trips t WHERE shape_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM shape_points s WHERE s.shape_id=t.shape_id)").fetchone()[0]
                report["consistency"]["trips_with_missing_shape"] = missing_shapes
                if missing_shapes and "shapes.txt" in names:
                    raise ValueError(f"{missing_shapes} trips reference missing shapes; existing database preserved")
        except Exception as error:
            if report_path:
                report["errors"].append(type(error).__name__ if isinstance(error, SQLAlchemyError) else str(error))
                failure = report_path.with_suffix(".failed.json")
                failure.parent.mkdir(parents=True, exist_ok=True)
                failure.write_text(json.dumps(report, indent=2))
            raise
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))
    return report
