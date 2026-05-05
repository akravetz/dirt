from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class CloudSite(SQLModel, table=True):
    __tablename__ = "cloud_site"

    site_id: str = Field(primary_key=True, max_length=80)
    name: str = Field(max_length=160)
    timezone: str = Field(default="America/Denver", max_length=80)
    is_active: bool = True
    gateway_last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_catalog_sync_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudTent(SQLModel, table=True):
    __tablename__ = "cloud_tent"
    __table_args__ = (UniqueConstraint("site_id", "tent_id"),)

    tent_key: str = Field(primary_key=True, max_length=180)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    name: str = Field(max_length=160)
    is_active: bool = True
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudZone(SQLModel, table=True):
    __tablename__ = "cloud_zone"
    __table_args__ = (UniqueConstraint("site_id", "tent_id", "zone_id"),)

    zone_key: str = Field(primary_key=True, max_length=260)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    zone_id: str = Field(index=True, max_length=80)
    name: str = Field(max_length=160)
    kind: str = Field(default="environment", max_length=80)
    is_active: bool = True
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudDevice(SQLModel, table=True):
    __tablename__ = "cloud_device"
    __table_args__ = (UniqueConstraint("site_id", "tent_id", "device_id"),)

    device_key: str = Field(primary_key=True, max_length=260)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    zone_id: str | None = Field(default=None, index=True, max_length=80)
    device_id: str = Field(index=True, max_length=120)
    name: str = Field(max_length=160)
    kind: str = Field(default="sensor", max_length=80)
    controller: str | None = Field(default=None, max_length=80)
    is_active: bool = True
    last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudCapability(SQLModel, table=True):
    __tablename__ = "cloud_capability"
    __table_args__ = (UniqueConstraint("site_id", "tent_id", "capability_id"),)

    capability_key: str = Field(primary_key=True, max_length=320)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    device_id: str = Field(index=True, max_length=120)
    capability_id: str = Field(index=True, max_length=160)
    metric_name: str | None = Field(default=None, max_length=120)
    kind: str = Field(default="metric", max_length=80)
    unit: str | None = Field(default=None, max_length=40)
    is_enabled: bool = True
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudLatestMetric(SQLModel, table=True):
    __tablename__ = "cloud_latest_metric"
    __table_args__ = (
        UniqueConstraint("site_id", "tent_id", "capability_id", "metric"),
    )

    metric_key: str = Field(primary_key=True, max_length=360)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    zone_id: str | None = Field(default=None, index=True, max_length=80)
    device_id: str | None = Field(default=None, index=True, max_length=120)
    capability_id: str = Field(index=True, max_length=160)
    metric: str = Field(index=True, max_length=120)
    value: float = Field(sa_column=Column(Float, nullable=False))
    unit: str | None = Field(default=None, max_length=40)
    source_updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    received_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    stale_after_s: int = 120


class CloudMetricRollup(SQLModel, table=True):
    __tablename__ = "cloud_metric_rollup"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "capability_id",
            "metric",
            "bucket",
            "bucket_start_at",
        ),
    )

    rollup_key: str = Field(primary_key=True, max_length=480)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    capability_id: str = Field(index=True, max_length=160)
    metric: str = Field(index=True, max_length=120)
    bucket: str = Field(index=True, max_length=40)
    bucket_start_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    bucket_end_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    min_value: float | None = None
    avg_value: float | None = None
    max_value: float | None = None
    sample_count: int = 0
    unit: str | None = Field(default=None, max_length=40)
    received_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudAsset(SQLModel, table=True):
    __tablename__ = "cloud_asset"
    __table_args__ = (UniqueConstraint("site_id", "tent_id", "object_key"),)

    asset_id: str = Field(primary_key=True, max_length=160)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    zone_id: str | None = Field(default=None, index=True, max_length=80)
    device_id: str | None = Field(default=None, index=True, max_length=120)
    kind: str = Field(default="snapshot", max_length=40)
    object_key: str = Field(index=True, max_length=500)
    content_type: str = Field(max_length=120)
    byte_size: int
    sha256: str | None = Field(default=None, max_length=64)
    captured_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    uploaded_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    signed_url_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class CloudCommand(SQLModel, table=True):
    __tablename__ = "cloud_command"
    __table_args__ = (
        UniqueConstraint("requested_by", "idempotency_key"),
        Index("ix_cloud_command_claimable", "site_id", "status", "expires_at"),
    )

    command_id: str = Field(primary_key=True, max_length=80)
    idempotency_key: str = Field(index=True, max_length=160)
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    device_id: str | None = Field(default=None, max_length=120)
    capability_id: str | None = Field(default=None, max_length=160)
    command_type: str = Field(index=True, max_length=80)
    payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    requested_by: str = Field(index=True, max_length=160)
    status: str = Field(default="queued", index=True, max_length=40)
    queued_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    claimed_by: str | None = Field(default=None, max_length=120)
    claimed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    finished_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudAuditEvent(SQLModel, table=True):
    __tablename__ = "cloud_audit_event"

    event_id: str = Field(primary_key=True, max_length=80)
    site_id: str | None = Field(default=None, index=True, max_length=80)
    actor_type: str = Field(max_length=40)
    actor_id: str | None = Field(default=None, max_length=160)
    event_type: str = Field(index=True, max_length=120)
    subject_type: str | None = Field(default=None, max_length=80)
    subject_id: str | None = Field(default=None, max_length=160)
    event_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class GatewayCredential(SQLModel, table=True):
    __tablename__ = "gateway_credential"

    credential_id: str = Field(primary_key=True, max_length=120)
    gateway_id: str = Field(index=True, max_length=120)
    token_sha256: str = Field(index=True, max_length=64)
    allowed_site_id: str = Field(index=True, max_length=80)
    is_active: bool = True
    last_used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    rotated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
