import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.core.config import Settings
from app.db.database import make_engine, normalize_database_url
from app.main import create_app
from app.services.gtfs_service import import_gtfs
from test_regressions import make_feed


def test_neon_url_selects_psycopg_and_preserves_credentials_and_tls():
    supplied = "postgresql://example:p%40ss%3Aword@ep-example-pooler.neon.tech/db?sslmode=require&channel_binding=require"
    url = normalize_database_url(supplied)
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss:word"
    assert dict(url.query) == {"sslmode": "require", "channel_binding": "require"}
    assert normalize_database_url(url) == url
    assert "p%40ss" not in repr(Settings(supplied, (), "INFO"))
    engine = make_engine(supplied)
    try:
        assert engine.dialect.driver == "psycopg"
        _, kwargs = engine.dialect.create_connect_args(engine.url)
        assert kwargs["sslmode"] == "require"
    finally:
        engine.dispose()


def test_sqlite_url_creates_local_database(tmp_path):
    path = tmp_path / "nested" / "local.db"
    engine = make_engine(f"sqlite+pysqlite:///{path}")
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
        assert path.is_file()
    finally:
        engine.dispose()


@pytest.fixture
def postgres_url():
    value = os.environ.get("SAFARNAMA_TEST_POSTGRES_URL")
    if not value:
        pytest.skip("Set SAFARNAMA_TEST_POSTGRES_URL to an isolated local PostgreSQL database")
    url = normalize_database_url(value)
    host = url.query.get("host", url.host)
    assert isinstance(host, str) and (host in {"localhost", "127.0.0.1", "::1"} or host.startswith("/"))
    assert "hostaddr" not in url.query and "service" not in url.query
    assert url.drivername == "postgresql+psycopg"
    schema = "safarnama_test_" + uuid4().hex
    engine = make_engine(url)
    try:
        with engine.begin() as db:
            addr = db.scalar(text("SELECT inet_server_addr()"))
            assert addr is None or str(addr) in {"127.0.0.1", "::1"}
            db.exec_driver_sql(f"CREATE SCHEMA {schema}")
        try:
            yield url.update_query_dict({"options": f"-csearch_path={schema}"})
        finally:
            with engine.begin() as db:
                db.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
    finally:
        engine.dispose()


def test_postgres_bootstrap_and_empty_readiness(postgres_url):
    settings = Settings(postgres_url.render_as_string(hide_password=False), (), "WARNING")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert {"stops", "routes", "trips", "stop_times"} <= set(
            inspect(client.app.state.engine).get_table_names()
        )


def test_postgres_import_validation_replacement_and_api(postgres_url, tmp_path):
    feed = make_feed(
        tmp_path,
        times=["T,25:00:00,25:00:00,A,0", "T,24:55:00,24:55:00,A,0",
               "T,25:10:00,25:10:00,B,1", "T,25:15:00,25:15:00,UNKNOWN,2",
               "T,25:20:00,25:20:00,B,2147483648"],
        dates=["S,20261124,2"],
    )
    report_path = tmp_path / "import.json"
    report = import_gtfs(feed, report_path=report_path, database_url=postgres_url)
    assert json.loads(report_path.read_text()) == report
    stats = report["tables"]["stop_times.txt"]
    assert (stats["imported"], stats["duplicates"], stats["rejected"]) == (2, 1, 2)
    assert stats["validation_errors"]["integer field outside PostgreSQL integer range"] == 1
    with pytest.raises(ValueError, match="already contains GTFS rows"):
        import_gtfs(feed, database_url=postgres_url)
    bad_feed = make_feed(
        tmp_path,
        times=["T,08:10:00,08:10:00,A,0", "T,08:00:00,08:00:00,B,1"],
    )
    with pytest.raises(ValueError, match="run backward"):
        import_gtfs(bad_feed, report_path=report_path, database_url=postgres_url, replace=True)
    assert json.loads(report_path.read_text()) == report
    assert json.loads((tmp_path / "import.failed.json").read_text())["consistency"]["out_of_order_stop_times"] == 1

    app = create_app(Settings(postgres_url.render_as_string(hide_password=False), (), "WARNING"))
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200
        api = "/api/v1"
        assert client.get(f"{api}/stops", params={"q": "ALPHA"}).json()[0]["id"] == "A"
        assert client.get(f"{api}/routes", params={"q": "BUS R"}).json()[0]["shortName"] == "Bus R"
        assert client.get(f"{api}/routes/R").json()["agencyId"] == "X"
        assert client.get(f"{api}/routes/R/trips").json()[0]["serviceId"] == "S"
        assert len(client.get(f"{api}/routes/R/stops").json()) == 2
        assert len(client.get(f"{api}/routes/R/geometry").json()["coordinates"]) == 2
        query = {"origin": "A", "destination": "B", "date": "2026-11-24", "time": "00:55", "mode": "historical"}
        journeys = client.get(f"{api}/journeys", params=query).json()
        assert journeys[0]["departure"] == 60
        # A calendar removal for the previous GTFS service day suppresses the overnight run.
        assert client.get(f"{api}/journeys", params={**query, "date": "2026-11-25"}).json() == []
        analytics = client.get(f"{api}/analytics").json()
        assert analytics["counts"]["stopTimes"] == 2
        assert analytics["scheduledDeparturesByHour"][25]["trips"] == 1

    replacement = make_feed(tmp_path)
    updated = import_gtfs(replacement, database_url=postgres_url, replace=True)
    assert updated["tables"]["stop_times.txt"]["imported"] == 2
    assert updated["tables"]["stop_times.txt"]["duplicates"] == 0
