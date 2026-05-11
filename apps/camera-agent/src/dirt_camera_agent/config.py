from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dirt_shared.config import DEFAULT_CAMERA_SOCKET_PATH

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parents[4]
SUPPORTED_CAMERA_AGENT_SOURCE = "obsbot-daemon"


class CameraAgentSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    source: str = Field(
        default=SUPPORTED_CAMERA_AGENT_SOURCE,
        validation_alias="DIRT_CAMERA_AGENT_SOURCE",
    )
    site_id: str = Field(validation_alias="DIRT_SITE_ID")
    tent_id: str = Field(validation_alias="DIRT_TENT_ID")
    camera_device_id: str = Field(validation_alias="DIRT_CAMERA_DEVICE_ID")
    camera_view_id: str | None = Field(
        default=None, validation_alias="DIRT_CAMERA_VIEW_ID"
    )
    camera_kind: str = Field(default="snapshot", validation_alias="DIRT_CAMERA_KIND")
    capture_interval_s: float = Field(
        default=300.0, gt=0, validation_alias="DIRT_CAMERA_CAPTURE_INTERVAL_S"
    )
    spool_dir: Path | None = Field(
        default=None, validation_alias="DIRT_CAMERA_SPOOL_DIR"
    )
    data_dir: Path = Field(default=_REPO_ROOT / "var", validation_alias="DIRT_DATA_DIR")
    camera_socket_path: Path | None = Field(
        default=None, validation_alias="DIRT_CAMERA_SOCKET"
    )
    xdg_runtime_dir: Path | None = Field(
        default=None, validation_alias="XDG_RUNTIME_DIR"
    )
    cloud_api_base_url: str = Field(
        default="http://127.0.0.1:8002", validation_alias="DIRT_CLOUD_API_BASE_URL"
    )
    cloud_gateway_id: str = Field(
        default="gateway-camera-agent", validation_alias="DIRT_CLOUD_GATEWAY_ID"
    )
    cloud_gateway_token: str = Field(
        default="", validation_alias="DIRT_CLOUD_GATEWAY_TOKEN"
    )

    @model_validator(mode="after")
    def _derive_paths(self) -> CameraAgentSettings:
        if self.spool_dir is None:
            self.spool_dir = self.data_dir / "camera-agent" / self.tent_id / "snapshots"
        if self.camera_socket_path is None:
            self.camera_socket_path = (
                self.xdg_runtime_dir / "dirt-camera.sock"
                if self.xdg_runtime_dir is not None
                else DEFAULT_CAMERA_SOCKET_PATH
            )
        return self

    def validate_source(self) -> None:
        if self.source != SUPPORTED_CAMERA_AGENT_SOURCE:
            raise ValueError(
                "unsupported camera agent source "
                f"{self.source!r}; supported source: {SUPPORTED_CAMERA_AGENT_SOURCE}"
            )
