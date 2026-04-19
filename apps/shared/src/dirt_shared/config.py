from __future__ import annotations

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

# Germination date per wiki/overview.md. Day 1 = 2026-03-15. Seeds the
# grow_state.germination_date row on first boot — runtime reads go through
# dirt_shared.services.grow_state so a future UI can edit the date in one place.
GROW_START = date(2026, 3, 15)


class Settings(BaseSettings):
    app_name: str = "Dirt"
    auth_username: str = "admin"
    auth_password: str = "changeme"
    # Runtime data directory: dirt.db + snapshots/ + archives/ + logs/ +
    # sessions/ all live under this. Override via DIRT_DATA_DIR env var.
    # Default is the post-cutover target (<repo>/var). Pre-cutover, the
    # running service overrides DATABASE_URL + SNAPSHOT_DIR in .env to point
    # at the repo-root files; removing those two env vars at cutover lets
    # the derivation below move everything under <repo>/var in one step.
    data_dir: Path = Field(default=_REPO_ROOT / "var", validation_alias="DIRT_DATA_DIR")
    # None = derive from data_dir in _derive_data_paths. Set explicitly to
    # override independently of data_dir.
    database_url: str | None = None
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
    # Control targets VPD (not fixed RH); the active band comes from
    # services.grow_state.current_targets() and shifts by stage.
    kasa_username: str = ""
    kasa_password: str = ""
    kasa_humidifier_host: str = "192.168.1.220"
    vpd_deadband_kpa: float = 0.1
    # Subtracted from the day VPD band during lights-off to let the loop
    # rest rather than chase the cooling-air VPD drop. See
    # wiki/decisions/2026-04-19-lights-off-aware-humidifier.md.
    vpd_lights_off_offset_kpa: float = -0.3
    # Pre-lights-off window during which the humidifier is forced off to
    # prevent dosing mist into air that's about to cool.
    lights_off_prep_minutes: int = 30
    humidifier_poll_interval: int = 30
    humidifier_failsafe_stale_seconds: int = 300
    # Telegram bot. Outbound-only for V1 (daily report); inbound channel TBD.
    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""
    # Daily report. See wiki/CLAUDE.md daily update workflow.
    daily_report_photo_settle_s: float = 1.5
    daily_report_max_capture_age_ms: int = 400
    daily_report_sensor_min_raw: float = 30.0
    daily_report_sensor_max_raw: float = 4000.0
    daily_report_sensor_max_age_s: int = 300

    @model_validator(mode="after")
    def _derive_data_paths(self) -> Settings:
        if self.database_url is None:
            self.database_url = (
                f"sqlite+aiosqlite:///{(self.data_dir / 'dirt.db').as_posix()}"
            )
        if self.snapshot_dir is None:
            self.snapshot_dir = self.data_dir / "snapshots"
        if self.archive_dir is None:
            self.archive_dir = self.data_dir / "archives"
        return self


settings = Settings()
