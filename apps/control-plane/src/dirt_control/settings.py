from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class CloudSettings(BaseSettings):
    """Runtime settings for the hosted control-plane API."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    database_url: str = Field(
        validation_alias=AliasChoices("DIRT_CLOUD_DATABASE_URL", "DATABASE_URL")
    )
    admin_username: str = Field(alias="DIRT_CLOUD_ADMIN_USERNAME")
    admin_password_hash: str = Field(alias="DIRT_CLOUD_ADMIN_PASSWORD_HASH")
    session_secret: str = Field(alias="DIRT_CLOUD_SESSION_SECRET", min_length=16)
    session_cookie_secure: bool = Field(
        default=True, alias="DIRT_CLOUD_SESSION_COOKIE_SECURE"
    )
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="DIRT_CLOUD_ALLOWED_ORIGINS"
    )
    default_site_id: str = Field(default="homebox", alias="DIRT_CLOUD_SITE_ID")
    upload_url_ttl_s: int = Field(default=900, alias="DIRT_CLOUD_UPLOAD_URL_TTL_S")
    asset_url_ttl_s: int = Field(default=300, alias="DIRT_CLOUD_ASSET_URL_TTL_S")
    asset_retention_days: int = Field(
        default=30, alias="DIRT_CLOUD_ASSET_RETENTION_DAYS"
    )
    command_creation_enabled: bool = Field(
        default=True, alias="DIRT_CLOUD_COMMAND_CREATION_ENABLED"
    )
    gateway_command_claim_enabled: bool = Field(
        default=True, alias="DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED"
    )
    bucket_name: str = Field(default="dirt-assets", alias="DIRT_CLOUD_BUCKET_NAME")
    s3_endpoint: str | None = Field(default=None, alias="DIRT_CLOUD_S3_ENDPOINT")
    s3_region: str | None = Field(default=None, alias="DIRT_CLOUD_S3_REGION")
    s3_access_key_id: str | None = Field(
        default=None, alias="DIRT_CLOUD_S3_ACCESS_KEY_ID"
    )
    s3_secret_access_key: str | None = Field(
        default=None, alias="DIRT_CLOUD_S3_SECRET_ACCESS_KEY"
    )
    public_asset_base_url: str = Field(
        default="https://storage.invalid", alias="DIRT_CLOUD_ASSET_PUBLIC_BASE_URL"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item) for item in value]
        raise TypeError("allowed origins must be a comma-separated string or list")


def normalize_async_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url
