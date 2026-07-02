from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
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
    __table_args__ = (
        UniqueConstraint("site_id", name="cloud_site_site_id_key"),
        UniqueConstraint(
            "site_id",
            "source_site_id",
            name="uq_cloud_site_site_source_site",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(max_length=80)
    source_site_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
        UniqueConstraint(
            "site_id",
            "source_tent_id",
            name="uq_cloud_tent_site_source_tent",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_site_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    name: str = Field(max_length=160)
    role: str | None = Field(default=None, max_length=80)
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
            "source_zone_id",
            name="uq_cloud_zone_site_source_zone",
        ),
        Index("ix_cloud_zone_site_source_tent", "site_id", "source_tent_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_zone_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
        Index(
            "ux_cloud_device_site_source_tent_device",
            "site_id",
            "source_tent_id",
            "device_id",
            unique=True,
        ),
        Index("ix_cloud_device_site_source_zone", "site_id", "source_zone_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_zone_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
        Index(
            "ux_cloud_capability_site_source_tent_device_cap",
            "site_id",
            "source_tent_id",
            "device_id",
            "capability_id",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
            "source_schedule_id",
            name="uq_cloud_schedule_site_source_schedule",
        ),
        Index(
            "ix_cloud_schedule_site_source_tent_kind",
            "site_id",
            "source_tent_id",
            "kind",
        ),
        Index("ix_cloud_schedule_site_source_zone", "site_id", "source_zone_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_site_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_zone_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_schedule_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    device_id: str | None = Field(default=None, index=True, max_length=120)
    capability_id: str | None = Field(default=None, index=True, max_length=160)
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


class CloudPlantLine(SQLModel, table=True):
    __tablename__ = "cloud_plant_line"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_line_id",
            name="uq_cloud_plant_line_site_source_line",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_line_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    project_code: str | None = Field(default=None, max_length=80)
    generation_label: str | None = Field(default=None, max_length=80)
    strain: str = Field(max_length=160)
    cultivar: str = Field(max_length=160)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_name: str | None = Field(default=None, max_length=160)
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudSeedLot(SQLModel, table=True):
    __tablename__ = "cloud_seed_lot"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_seed_lot_id",
            name="uq_cloud_seed_lot_site_source_seed_lot",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_seed_lot_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    line_source_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    sex_type_key: str = Field(
        default="unknown",
        sa_column=Column(String(40), nullable=False, server_default="unknown"),
    )
    is_purchased: bool = False
    vendor_name: str | None = Field(default=None, max_length=160)
    acquired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    produced_by_cross_event_source_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    seed_count: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
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
            "source_plant_id",
            name="uq_cloud_plant_site_source_plant",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_plant_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    line_source_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    sex_key: str = Field(
        default="unknown",
        sa_column=Column(String(40), nullable=False, server_default="unknown"),
    )
    source_seed_lot_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    clone_source_plant_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    key: str = Field(index=True, max_length=120)
    name: str = Field(max_length=160)
    germinated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    taken_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when a cutting was taken from its mother plant; clone "
                "propagation fact independent from rooting."
            ),
        ),
    )
    rooted_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when a clone cutting was observed rooted; independent "
                "from when the cutting was taken."
            ),
        ),
    )
    veg_started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    flower_started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    culled_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    culled_reason: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    harvested_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    selected_for_breeding_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    selected_for_breeding_reason: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
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


class CloudPlantSexTest(SQLModel, table=True):
    __tablename__ = "cloud_plant_sex_test"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_sex_test_id",
            name="uq_cloud_plant_sex_test_site_source_test",
        ),
        UniqueConstraint(
            "site_id",
            "vendor_name",
            "vendor_test_code",
            name="uq_cloud_plant_sex_test_site_vendor_code",
        ),
        Index(
            "ix_cloud_plant_sex_test_site_source_plant",
            "site_id",
            "source_plant_id",
        ),
        Index(
            "ix_cloud_plant_sex_test_site_result_received",
            "site_id",
            "result_received_at",
        ),
        CheckConstraint(
            "result_sex_key IS NULL OR result_sex_key IN ('male', 'female')",
            name="ck_cloud_plant_sex_test_result_sex_key_lab_result",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_sex_test_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_plant_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    vendor_name: str = Field(max_length=160)
    assay_name: str | None = Field(default=None, max_length=160)
    vendor_test_code: str = Field(max_length=160)
    sample_collected_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    sample_sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    result_received_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    result_sex_key: str | None = Field(default=None, max_length=40)
    is_inconclusive: bool = False
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudPlantLocation(SQLModel, table=True):
    __tablename__ = "cloud_plant_location"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_location_id",
            name="uq_cloud_plant_location_site_source_location",
        ),
        Index(
            "ix_cloud_plant_location_current_tent",
            "site_id",
            "source_tent_id",
            "grid_position",
            "source_plant_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_location_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_plant_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    grid_position: str | None = Field(default=None, max_length=80)
    start_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    end_at: datetime | None = Field(
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


class CloudCrossEvent(SQLModel, table=True):
    __tablename__ = "cloud_cross_event"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_cross_event_id",
            name="uq_cloud_cross_event_site_source_cross_event",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_cross_event_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    resulting_line_source_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    seed_parent_source_plant_id: int = Field(
        sa_column=Column(BigInteger, nullable=False)
    )
    pollen_parent_source_plant_id: int = Field(
        sa_column=Column(BigInteger, nullable=False)
    )
    pollinated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    pollen_parent_is_reversed: bool | None = None
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudPlantNote(SQLModel, table=True):
    __tablename__ = "cloud_plant_note"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_note_id",
            name="uq_cloud_plant_note_site_source_note",
        ),
        Index(
            "ix_cloud_plant_note_plant_observed_at",
            "site_id",
            "source_plant_id",
            "observed_at",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_note_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_plant_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    observed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_by: str | None = Field(default=None, max_length=160)
    synced_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class CloudPlantEvent(SQLModel, table=True):
    __tablename__ = "cloud_plant_event"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_event_id",
            name="uq_cloud_plant_event_site_source_event",
        ),
        Index(
            "ix_cloud_plant_event_plant_occurred_at",
            "site_id",
            "source_plant_id",
            "occurred_at",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_event_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_plant_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    is_pollen_collection: bool = False
    is_seed_production: bool = False
    is_clone_taken: bool = False
    is_sex_observation: bool = False
    is_reversal: bool = False
    is_transplant: bool = False
    is_selection_for_breeding: bool = False
    occurred_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=False)
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


class CloudPlantMetricStream(SQLModel, table=True):
    __tablename__ = "cloud_plant_metric_stream"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "source_plant_id",
            "device_id",
            "capability_id",
            "metric",
            name="uq_cloud_plant_metric_stream_identity",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_plant_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    device_id: str = Field(index=True, max_length=120)
    capability_id: str = Field(index=True, max_length=160)
    metric: str = Field(index=True, max_length=120)
    display_order: int = Field(sa_column=Column(Integer, nullable=False))
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
        Index(
            "ux_cloud_latest_metric_site_source_stream",
            "site_id",
            "source_tent_id",
            "device_id",
            "capability_id",
            "metric",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_site_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_zone_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
        Index(
            "ux_cloud_metric_rollup_site_source_stream_bucket",
            "site_id",
            "source_tent_id",
            "device_id",
            "capability_id",
            "metric",
            "bucket",
            "bucket_start_at",
            unique=True,
        ),
        Index(
            "ix_cloud_metric_rollup_site_source_metric_bucket",
            "site_id",
            "source_tent_id",
            "metric",
            "bucket",
            "bucket_start_at",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(index=True, max_length=80)
    source_site_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
        Index(
            "ux_cloud_asset_site_source_tent_object_key",
            "site_id",
            "source_tent_id",
            "object_key",
            unique=True,
        ),
        Index(
            "ix_cloud_asset_site_source_tent_captured",
            "site_id",
            "source_tent_id",
            "captured_at",
        ),
        Index(
            "ix_cloud_asset_site_source_zone_captured",
            "site_id",
            "source_zone_id",
            "captured_at",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    asset_id: str = Field(max_length=160)
    site_id: str = Field(index=True, max_length=80)
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    source_zone_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
    source_tent_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
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
