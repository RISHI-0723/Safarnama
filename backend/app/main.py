import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import BoundedSemaphore

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.ml_adapter import UnavailableAdapter
from app.adapters.live_transit import DelhiLiveTransit, DisabledLiveTransit
from app.api.live_transit import router as live_transit_router
from app.adapters.historical_demand import load_historical_demand
from app.api.historical_demand import router as historical_demand_router
from app.api.health import router as health_router, readiness, liveness
from app.api.stops import router as stops_router
from app.api.routes import router as routes_router
from app.api.crowding import router as crowding_router
from app.api.analytics import router as analytics_router
from app.api.journeys import router as journeys_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.request_metadata import RequestMetadataMiddleware
from app.db import models  # noqa: F401 - register tables with metadata
from app.db.database import initialize_database, make_engine, make_session_factory
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, clock=None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            with engine.begin() as connection:
                initialize_database(connection)
            app.state.historical_demand, app.state.demand_issue = load_historical_demand(
                settings.historical_artifact_dir, engine, settings.historical_route_mapping,
            )
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="SAFARNAMA API", version="0.1.0", lifespan=lifespan)
    app.state.clock = clock or (lambda: datetime.now(timezone.utc))
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.analytics = AnalyticsService(engine)
    app.state.historical_demand = None
    app.state.demand_issue = None
    app.state.crowding_adapter = UnavailableAdapter()
    app.state.live_transit = (DelhiLiveTransit(settings.live_api_key)
                              if settings.live_enabled and settings.live_api_key
                              else DisabledLiveTransit(settings.live_enabled))
    app.state.journey_slots = BoundedSemaphore(settings.journey_concurrency)
    app.add_middleware(RequestMetadataMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.add_api_route("/health", liveness, methods=["GET"], tags=["health"])
    app.add_api_route("/ready", readiness, methods=["GET"], tags=["health"])
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(stops_router, prefix="/api/v1")
    app.include_router(routes_router, prefix="/api/v1")
    app.include_router(crowding_router, prefix="/api/v1")
    app.include_router(historical_demand_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(live_transit_router, prefix="/api/v1")
    app.include_router(journeys_router, prefix="/api/v1")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, error: SQLAlchemyError):
        logger.error("Database operation failed request_id=%s error_type=%s",
                     _request.state.request_id, type(error).__name__)
        return JSONResponse(status_code=503, content={"detail": "Transit database unavailable"})

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, error: Exception):
        request_id = getattr(_request.state, "request_id", "")
        logger.error("Unhandled API error request_id=%s error_type=%s", request_id, type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"},
                            headers={"X-Request-ID": request_id} if request_id else None)

    return app


app = create_app()
