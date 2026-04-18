from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


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


settings = Settings()
