"""Runtime settings. Environment variables are read when the app is created."""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    cors_origins: tuple[str, ...]
    log_level: str
    historical_artifact_dir: Path | None = None
    historical_route_mapping: Path | None = None
    journey_concurrency: int = 4
    live_enabled: bool = False
    live_api_key: str | None = field(default=None, repr=False)


def get_settings() -> Settings:
    configured = os.getenv("SAFARNAMA_ML_ARTIFACT_DIR")
    default = Path(__file__).resolve().parents[3] / "ml" / "outputs"
    directory = default if configured is None else (Path(configured) if configured.strip() else None)
    mapping = os.getenv("SAFARNAMA_ML_ROUTE_MAPPING")
    concurrency = int(os.getenv("SAFARNAMA_JOURNEY_CONCURRENCY", "4"))
    if not 1 <= concurrency <= 32:
        raise ValueError("SAFARNAMA_JOURNEY_CONCURRENCY must be 1–32")
    return Settings(
        database_url=os.getenv("SAFARNAMA_DATABASE_URL", "sqlite:///./data/safarnama.db"),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "SAFARNAMA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        ),
        historical_artifact_dir=directory,
        historical_route_mapping=Path(mapping) if mapping else None,
        journey_concurrency=concurrency,
        live_enabled=os.getenv("SAFARNAMA_LIVE_ENABLED", "").lower() == "true",
        live_api_key=os.getenv("SAFARNAMA_DELHI_LIVE_KEY"),
        log_level=os.getenv("SAFARNAMA_LOG_LEVEL", "INFO").upper(),
    )
