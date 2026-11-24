import argparse
import json
import os
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.services.gtfs_service import import_gtfs


def main():
    parser = argparse.ArgumentParser(description="Validate and import static GTFS")
    parser.add_argument("zip_path", type=Path)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--database", type=Path, help="SQLite file (default: data/safarnama.db)")
    target.add_argument("--postgres", action="store_true", help="Read the PostgreSQL URL from SAFARNAMA_DATABASE_URL")
    parser.add_argument("--replace", action="store_true", help="Allow replacing an existing PostgreSQL feed")
    parser.add_argument("--report", type=Path, default=Path("data/ingestion_report.json"))
    args = parser.parse_args()
    database_url = os.getenv("SAFARNAMA_DATABASE_URL") if args.postgres else None
    if args.postgres and not database_url:
        parser.error("--postgres requires SAFARNAMA_DATABASE_URL")
    if args.replace and not args.postgres:
        parser.error("--replace applies only to --postgres")

    try:
        report = import_gtfs(
            args.zip_path, None if args.postgres else args.database or Path("data/safarnama.db"),
            args.report, database_url=database_url, replace=args.replace,
        )
    except SQLAlchemyError:
        parser.exit(1, "GTFS import failed during a database operation. Check the connection, permissions and failure report.\n")
    print(json.dumps({name: {key: value for key, value in stats.items() if key in ("total", "imported", "rejected", "duplicates")} for name, stats in report["tables"].items()}, indent=2))


if __name__ == "__main__":
    main()
