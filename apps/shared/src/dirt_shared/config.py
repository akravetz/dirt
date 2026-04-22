from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

load_dotenv()

# config.py lives at: apps/shared/src/dirt_shared/config.py
#   parents[0] = dirt_shared/
#   parents[1] = src/
#   parents[2] = shared/
#   parents[3] = apps/
#   parents[4] = <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[4]

# Germination date per wiki/overview.md. Day 1 = 2026-03-15. Seeded into
# growstate on the initial Atlas migration; runtime reads go through
# dirt_shared.services.grow_state so a future UI can edit the date in one place.
GROW_START = date(2026, 3, 15)


class Settings(BaseSettings):
    app_name: str = "Dirt"
    auth_username: str = "admin"
    auth_password: str = "changeme"
    # Runtime data directory: snapshots/ + archives/ + logs/ + sessions/
    # all live under this. Override via DIRT_DATA_DIR env var.
    data_dir: Path = Field(default=_REPO_ROOT / "var", validation_alias="DIRT_DATA_DIR")
    # Built SPA bundle served by dirt-web. Must contain index.html and an
    # assets/ subdirectory populated by `pnpm --dir web-ui build`. Override
    # via DIRT_WEB_UI_DIST_DIR (tests point this at a tmp_path fixture).
    web_ui_dist_dir: Path = Field(
        default=_REPO_ROOT / "web-ui" / "dist",
        validation_alias="DIRT_WEB_UI_DIST_DIR",
    )
    # Postgres — either set DATABASE_URL explicitly or provide the components
    # (DIRT_PG_{HOST,PORT,USER,PASSWORD,DATABASE}) and let _derive_db_url
    # assemble the async URL. No sqlite fallback post-cutover (ADR-006).
    database_url: str | None = None
    dirt_pg_host: str = Field(default="127.0.0.1", validation_alias="DIRT_PG_HOST")
    dirt_pg_port: int = Field(default=5432, validation_alias="DIRT_PG_PORT")
    dirt_pg_user: str = Field(default="dirt", validation_alias="DIRT_PG_USER")
    dirt_pg_password: str = Field(default="", validation_alias="DIRT_PG_PASSWORD")
    dirt_pg_database: str = Field(default="dirt", validation_alias="DIRT_PG_DATABASE")
    snapshot_dir: Path | None = None
    archive_dir: Path | None = None
    capture_interval: int = 300  # 5 minutes
    archive_retention_days: int = 7
    serial_port: str = "/dev/ttyArduino"
    serial_baud: int = 9600
    sensor_poll_interval: int = 20  # seconds
    secret_key: str = "change-me-in-production"
    mcp_bearer_token: str = "change-me-in-production"
    sensor_ingest_token: str = "change-me-in-production"
    # Voice channel. Empty defaults so non-voice deployments don't fail to boot;
    # dirt_voice.channels.voice validates presence at startup.
    deepgram_api_key: str = ""
    anthropic_api_key: str = ""
    elabs_api_key: str = ""
    elabs_voice_id: str = ""
    # Kasa EP10 humidifier plug. See wiki/hardware/humidifier-control.md.
    kasa_username: str = ""
    kasa_password: str = ""
    kasa_humidifier_host: str = "192.168.1.220"
    vpd_deadband_kpa: float = 0.1
    # Margin (minutes) around lights transitions during which the humidifier
    # is forced OFF — extends the off-window from `lights_off - margin` through
    # `lights_on - margin`. With the default 30 + a 23:00 → 05:00 dark cycle,
    # the humidifier is allowed to run only between 04:30 and 22:30.
    lights_off_prep_minutes: int = 30
    humidifier_poll_interval: int = 30
    humidifier_failsafe_stale_seconds: int = 300
    # Device watchdog — fires Telegram alerts on ok/warn → offline and
    # offline → ok transitions. 60s is prompt given the moisture-node
    # offline threshold is 5min. See services/device_watchdog.py.
    device_watchdog_poll_interval: int = 60
    # Telegram bot. Outbound-only for V1.
    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""
    # Daily report.
    daily_report_photo_settle_s: float = 1.5
    daily_report_max_capture_age_ms: int = 400
    daily_report_sensor_min_raw: float = 30.0
    daily_report_sensor_max_raw: float = 4000.0
    daily_report_sensor_max_age_s: int = 300

    @model_validator(mode="after")
    def _derive_data_paths(self) -> Settings:
        if self.database_url is None:
            # Assemble from DIRT_PG_* env vars.
            self.database_url = (
                f"postgresql+asyncpg://{self.dirt_pg_user}:{self.dirt_pg_password}"
                f"@{self.dirt_pg_host}:{self.dirt_pg_port}/{self.dirt_pg_database}"
            )
        if self.snapshot_dir is None:
            self.snapshot_dir = self.data_dir / "snapshots"
        if self.archive_dir is None:
            self.archive_dir = self.data_dir / "archives"
        return self

    # --- purpose-specific config slices ---
    # Each slice is what the corresponding service takes by constructor. Keeps
    # service signatures honest about what they actually depend on, and makes
    # test setup minimal (CaptureService(engine, CaptureConfig(snapshot_dir=tmp))).

    def capture(self) -> CaptureConfig:
        return CaptureConfig(
            snapshot_dir=Path(self.snapshot_dir),
            capture_interval=self.capture_interval,
        )

    def archive(self) -> ArchiveConfig:
        return ArchiveConfig(
            snapshot_dir=Path(self.snapshot_dir),
            archive_dir=Path(self.archive_dir),
            retention_days=self.archive_retention_days,
        )

    def humidifier(self) -> HumidifierConfig:
        return HumidifierConfig(
            kasa_username=self.kasa_username,
            kasa_password=self.kasa_password,
            kasa_humidifier_host=self.kasa_humidifier_host,
            vpd_deadband_kpa=self.vpd_deadband_kpa,
            lights_off_prep_minutes=self.lights_off_prep_minutes,
            poll_interval=self.humidifier_poll_interval,
            failsafe_stale_seconds=self.humidifier_failsafe_stale_seconds,
        )

    def serial(self) -> SerialConfig:
        return SerialConfig(
            port=self.serial_port,
            baud=self.serial_baud,
            poll_interval=self.sensor_poll_interval,
        )

    def auth(self) -> AuthConfig:
        return AuthConfig(
            username=self.auth_username,
            password=self.auth_password,
            secret_key=self.secret_key,
            sensor_ingest_token=self.sensor_ingest_token,
            mcp_bearer_token=self.mcp_bearer_token,
        )


@dataclass(frozen=True)
class CaptureConfig:
    snapshot_dir: Path
    capture_interval: int


@dataclass(frozen=True)
class ArchiveConfig:
    snapshot_dir: Path
    archive_dir: Path
    retention_days: int


@dataclass(frozen=True)
class HumidifierConfig:
    kasa_username: str
    kasa_password: str
    kasa_humidifier_host: str
    vpd_deadband_kpa: float
    lights_off_prep_minutes: int  # margin around lights transitions
    poll_interval: int
    failsafe_stale_seconds: int


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baud: int
    poll_interval: int


@dataclass(frozen=True)
class AuthConfig:
    username: str
    password: str
    secret_key: str
    sensor_ingest_token: str
    mcp_bearer_token: str
