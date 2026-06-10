from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Float,
    Identity,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class CloudSite(SQLModel, table=True):
    __tablename__ = "cloud_site"
    __table_args__ = (UniqueConstraint("site_id", name="cloud_site_site_id_key"),)

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(max_length=80)
    name: str = Field(max_length=160)
    timezone: str = Field(default="America/Denver", max_length=80)
    is_active: bool = True
    gateway_last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    gateway_backlog_depth: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
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
    __table_args__ = (
        UniqueConstraint("site_id", "tent_id", name="cloud_tent_site_id_tent_id_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
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
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "zone_id",
            name="cloud_zone_site_id_tent_id_zone_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
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
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "device_id",
            name="cloud_device_site_id_tent_id_device_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
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
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "device_id",
            "capability_id",
            name="cloud_capability_site_id_tent_id_device_id_capability_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
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


class CloudSchedule(SQLModel, table=True):
    __tablename__ = "cloud_schedule"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "schedule_id",
            name="cloud_schedule_site_id_tent_id_schedule_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    zone_id: str | None = Field(default=None, index=True, max_length=80)
    device_id: str | None = Field(default=None, index=True, max_length=120)
    capability_id: str | None = Field(default=None, index=True, max_length=160)
    schedule_id: str = Field(index=True, max_length=160)
    kind: str = Field(default="lights", max_length=80)
    starts_local: time = Field(sa_column=Column(Time, nullable=False))
    ends_local: time = Field(sa_column=Column(Time, nullable=False))
    timezone: str = Field(default="America/Denver", max_length=80)
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


class CloudPlant(SQLModel, table=True):
    __tablename__ = "cloud_plant"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "grow_run_id",
            "plant_id",
            name="cloud_plant_site_id_tent_id_grow_run_id_plant_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    grow_run_id: str = Field(index=True, max_length=160)
    plant_id: str = Field(index=True, max_length=80)
    name: str = Field(max_length=160)
    display_order: int = Field(sa_column=Column(Integer, nullable=False))
    sticker_color: str | None = Field(default=None, max_length=40)
    status: str = Field(max_length=40)
    purple: bool = False
    moisture_target_low: float = Field(sa_column=Column(Float, nullable=False))
    moisture_target_high: float = Field(sa_column=Column(Float, nullable=False))
    moisture_device_id: str | None = Field(default=None, index=True, max_length=120)
    moisture_capability_id: str | None = Field(default=None, index=True, max_length=160)
    wiki_path: str | None = Field(default=None, max_length=500)
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


class CloudWikiPage(SQLModel, table=True):
    __tablename__ = "cloud_wiki_page"
    __table_args__ = (
        UniqueConstraint("site_id", "path", name="cloud_wiki_page_site_id_path_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    path: str = Field(index=True, max_length=500)
    title: str = Field(max_length=300)
    frontmatter: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    body_markdown: str = Field(sa_column=Column(Text, nullable=False))
    sha256: str = Field(max_length=64)
    source_updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
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


class CloudLatestMetric(SQLModel, table=True):
    __tablename__ = "cloud_latest_metric"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "tent_id",
            "device_id",
            "capability_id",
            "metric",
            name="cloud_latest_metric_site_id_tent_id_device_id_capability_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    zone_id: str | None = Field(default=None, index=True, max_length=80)
    device_id: str = Field(index=True, max_length=120)
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
            "device_id",
            "capability_id",
            "metric",
            "bucket",
            "bucket_start_at",
            name="cloud_metric_rollup_site_id_tent_id_device_id_capability_id_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    tent_id: str = Field(index=True, max_length=80)
    device_id: str = Field(index=True, max_length=120)
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


class CloudMetricPresentation(SQLModel, table=True):
    __tablename__ = "cloud_metric_presentation"
    __table_args__ = (
        UniqueConstraint("metric", name="uq_cloud_metric_presentation_metric"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    metric: str = Field(sa_column=Column(String(120), nullable=False))
    display_name: str = Field(max_length=160)
    unit: str = Field(max_length=40)
    accent: str = Field(max_length=40)
    value_precision: int
    y_min: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    y_max: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    current_enabled: bool
    history_enabled: bool
    dashboard_group: str | None = Field(default=None, max_length=80)
    dashboard_group_label: str | None = Field(default=None, max_length=160)
    dashboard_group_order: int | None = None
    display_order: int


class CloudAsset(SQLModel, table=True):
    __tablename__ = "cloud_asset"
    __table_args__ = (
        UniqueConstraint("asset_id", name="cloud_asset_asset_id_key"),
        UniqueConstraint(
            "site_id",
            "tent_id",
            "object_key",
            name="cloud_asset_site_id_tent_id_object_key_key",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    asset_id: str = Field(max_length=160)
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
        UniqueConstraint("command_id", name="cloud_command_command_id_key"),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="cloud_command_requested_by_idempotency_key_key",
        ),
        Index("ix_cloud_command_claimable", "site_id", "status", "expires_at"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    command_id: str = Field(max_length=80)
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
    __table_args__ = (
        UniqueConstraint("event_id", name="cloud_audit_event_event_id_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    event_id: str = Field(max_length=80)
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
    __table_args__ = (
        UniqueConstraint("credential_id", name="gateway_credential_credential_id_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    credential_id: str = Field(max_length=120)
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
