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
    capture_interval: int = 900  # 15 minutes
    archive_dir: str = "archives"
    archive_retention_days: int = 7
    camera_device: int = 0
    camera_white_balance: int = 4500  # Fixed WB temp in Kelvin (2000-6500)
    camera_exposure: int = 15  # Initial manual exposure (3-2047)
    camera_gain: int = 0  # Sensor gain (0-255, lower=less amplification)
    camera_target_brightness: int = 150  # Target mean brightness (0-255)
    secret_key: str = "change-me-in-production"


settings = Settings()
