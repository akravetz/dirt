from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Germination date per wiki/overview.md. Day 1 = 2026-03-15. Seeds the
# grow_state.germination_date row on first boot — runtime reads go through
# dirt.services.grow_state so a future UI can edit the date in one place.
GROW_START = date(2026, 3, 15)


class Settings(BaseSettings):
    app_name: str = "Dirt"
    auth_username: str = "admin"
    auth_password: str = "changeme"
    database_url: str = "sqlite+aiosqlite:///dirt.db"
    snapshot_dir: str = "snapshots"
    capture_interval: int = 300  # 5 minutes
    archive_dir: str = "archives"
    archive_retention_days: int = 7
    serial_port: str = "/dev/ttyArduino"
    serial_baud: int = 9600
    sensor_poll_interval: int = 20  # seconds
    secret_key: str = "change-me-in-production"
    mcp_bearer_token: str = "change-me-in-production"
    sensor_ingest_token: str = "change-me-in-production"
    # Voice channel. Empty defaults so non-voice deployments don't fail to boot;
    # dirt.channels.voice validates presence at startup.
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
    humidifier_poll_interval: int = 30
    humidifier_min_off_seconds: int = 90
    humidifier_max_on_seconds: int = 1200
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


settings = Settings()
