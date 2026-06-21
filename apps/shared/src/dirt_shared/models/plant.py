"""Durable plant, breeding provenance, location, note, and event records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PlantLkuSex(SQLModel, table=True):
    """Controlled plant sex values with display and semantic metadata."""

    __tablename__ = "plant_lku_sex"
    __table_args__ = {
        "comment": "Controlled plant sex values with display and semantic metadata."
    }

    key: str = Field(
        sa_column=Column(
            Text,
            primary_key=True,
            comment="Controlled plant sex lookup key referenced by plant.sex_key.",
        )
    )
    display_name: str = Field(sa_column=Column(Text, nullable=False))
    display_order: int = Field(sa_column=Column(Integer, nullable=False))
    is_male: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_female: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_intersex: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_reversed: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )


class SeedLotLkuSexType(SQLModel, table=True):
    """Controlled seed-lot sex type values with display and semantic metadata."""

    __tablename__ = "seed_lot_lku_sex_type"
    __table_args__ = {
        "comment": (
            "Controlled seed-lot sex type values with display and semantic metadata."
        )
    }

    key: str = Field(
        sa_column=Column(
            Text,
            primary_key=True,
            comment=(
                "Controlled seed-lot sex type lookup key referenced by "
                "seed_lot.sex_type_key."
            ),
        )
    )
    display_name: str = Field(sa_column=Column(Text, nullable=False))
    display_order: int = Field(sa_column=Column(Integer, nullable=False))
    is_feminized: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_regular: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )


class PlantLine(SQLModel, table=True):
    __tablename__ = "plant_line"
    __table_args__ = (
        UniqueConstraint(
            "project_code",
            "generation_label",
            "strain",
            "cultivar",
            name="uq_plant_line_identity",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "project_code IS NULL OR btrim(project_code) <> ''",
            name="ck_plant_line_project_code_not_blank",
        ),
        CheckConstraint(
            "generation_label IS NULL OR btrim(generation_label) <> ''",
            name="ck_plant_line_generation_label_not_blank",
        ),
        CheckConstraint("btrim(strain) <> ''", name="ck_plant_line_strain_not_blank"),
        CheckConstraint(
            "btrim(cultivar) <> ''", name="ck_plant_line_cultivar_not_blank"
        ),
        CheckConstraint(
            "description IS NULL OR btrim(description) <> ''",
            name="ck_plant_line_description_not_blank",
        ),
        CheckConstraint(
            "source_name IS NULL OR btrim(source_name) <> ''",
            name="ck_plant_line_source_name_not_blank",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    project_code: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    generation_label: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    strain: str = Field(sa_column=Column(Text, nullable=False))
    cultivar: str = Field(sa_column=Column(Text, nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_name: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class CrossEvent(SQLModel, table=True):
    __tablename__ = "cross_event"
    __table_args__ = (
        CheckConstraint(
            "seed_parent_plant_id <> pollen_parent_plant_id",
            name="ck_cross_event_distinct_parents",
        ),
        CheckConstraint(
            "notes IS NULL OR btrim(notes) <> ''",
            name="ck_cross_event_notes_not_blank",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    resulting_line_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "plant_line.id",
                name="fk_cross_event_resulting_line",
                ondelete="RESTRICT",
            ),
            nullable=False,
        )
    )
    seed_parent_plant_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "plant.id",
                name="fk_cross_event_seed_parent",
                ondelete="RESTRICT",
                use_alter=True,
            ),
            nullable=False,
        )
    )
    pollen_parent_plant_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "plant.id",
                name="fk_cross_event_pollen_parent",
                ondelete="RESTRICT",
                use_alter=True,
            ),
            nullable=False,
        )
    )
    pollinated_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    pollen_parent_is_reversed: bool | None = Field(
        default=None, sa_column=Column(Boolean, nullable=True)
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class SeedLot(SQLModel, table=True):
    __tablename__ = "seed_lot"
    __table_args__ = (
        CheckConstraint(
            "NOT (is_purchased AND produced_by_cross_event_id IS NOT NULL)",
            name="ck_seed_lot_not_purchased_and_produced",
        ),
        CheckConstraint(
            "NOT is_purchased OR "
            "(vendor_name IS NOT NULL AND btrim(vendor_name) <> '')",
            name="ck_seed_lot_vendor_for_purchased",
        ),
        CheckConstraint(
            "is_purchased OR vendor_name IS NULL",
            name="ck_seed_lot_vendor_only_when_purchased",
        ),
        CheckConstraint(
            "seed_count IS NULL OR seed_count >= 0",
            name="ck_seed_lot_seed_count_positive",
        ),
        CheckConstraint(
            "notes IS NULL OR btrim(notes) <> ''",
            name="ck_seed_lot_notes_not_blank",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    line_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("plant_line.id", name="fk_seed_lot_line", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    sex_type_key: str = Field(
        default="unknown",
        sa_column=Column(
            Text,
            ForeignKey(
                "seed_lot_lku_sex_type.key",
                name="fk_seed_lot_sex_type",
                ondelete="RESTRICT",
            ),
            nullable=False,
            server_default=text("'unknown'"),
            comment=(
                "Lookup-backed controlled seed-lot sex type used for display and "
                "semantic branching metadata."
            ),
        ),
    )
    is_purchased: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    vendor_name: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    acquired_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    produced_by_cross_event_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "cross_event.id",
                name="fk_seed_lot_cross_event",
                ondelete="RESTRICT",
                use_alter=True,
            ),
            nullable=True,
        ),
    )
    is_produced: bool | None = Field(
        default=None,
        sa_column=Column(
            Boolean,
            Computed("produced_by_cross_event_id IS NOT NULL", persisted=True),
            nullable=False,
        ),
    )
    seed_count: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class Plant(SQLModel, table=True):
    __tablename__ = "plant"
    __table_args__ = (
        UniqueConstraint("key", name="uq_plant_key"),
        CheckConstraint("btrim(key) <> ''", name="ck_plant_key_not_blank"),
        CheckConstraint("btrim(name) <> ''", name="ck_plant_name_not_blank"),
        CheckConstraint(
            "source_seed_lot_id IS NULL OR clone_source_plant_id IS NULL",
            name="ck_plant_seed_or_clone_not_both",
        ),
        CheckConstraint(
            "clone_source_plant_id IS NULL OR clone_source_plant_id <> id",
            name="ck_plant_not_self_clone",
        ),
        CheckConstraint(
            "source_seed_lot_id IS NULL OR rooted_at IS NULL",
            name="ck_plant_seed_not_rooted_as_clone",
        ),
        CheckConstraint(
            "source_seed_lot_id IS NULL OR taken_at IS NULL",
            name="ck_plant_seed_not_taken_as_clone",
        ),
        CheckConstraint(
            "clone_source_plant_id IS NULL OR germinated_at IS NULL",
            name="ck_plant_clone_not_germinated",
        ),
        CheckConstraint(
            """
            (culled_at IS NULL AND culled_reason IS NULL)
            OR (
                culled_at IS NOT NULL
                AND culled_reason IS NOT NULL
                AND btrim(culled_reason) <> ''
            )
            """,
            name="ck_plant_culled_reason_required",
        ),
        CheckConstraint(
            "culled_at IS NULL OR harvested_at IS NULL",
            name="ck_plant_culled_or_harvested_not_both",
        ),
        CheckConstraint(
            "selected_for_breeding_reason IS NULL OR "
            "btrim(selected_for_breeding_reason) <> ''",
            name="ck_plant_selection_reason_not_blank",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    key: str = Field(
        sa_column=Column(
            Text,
            nullable=False,
            comment=(
                "Unique human-readable plant identifier printed on tags and used "
                "in notes/photos, e.g. SBBS-R1-001."
            ),
        )
    )
    line_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("plant_line.id", name="fk_plant_line", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    sex_key: str = Field(
        default="unknown",
        sa_column=Column(
            Text,
            ForeignKey(
                "plant_lku_sex.key",
                name="fk_plant_sex",
                ondelete="RESTRICT",
            ),
            nullable=False,
            server_default=text("'unknown'"),
            comment=(
                "Lookup-backed controlled plant sex value used for display and "
                "semantic branching metadata."
            ),
        ),
    )
    source_seed_lot_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "seed_lot.id",
                name="fk_plant_source_seed_lot",
                ondelete="RESTRICT",
                use_alter=True,
            ),
            nullable=True,
        ),
    )
    clone_source_plant_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "plant.id",
                name="fk_plant_clone_source",
                ondelete="RESTRICT",
                use_alter=True,
            ),
            nullable=True,
        ),
    )
    is_seed_grown: bool | None = Field(
        default=None,
        sa_column=Column(
            Boolean,
            Computed("source_seed_lot_id IS NOT NULL", persisted=True),
            nullable=False,
        ),
    )
    is_clone: bool | None = Field(
        default=None,
        sa_column=Column(
            Boolean,
            Computed("clone_source_plant_id IS NOT NULL", persisted=True),
            nullable=False,
        ),
    )
    name: str = Field(sa_column=Column(Text, nullable=False))
    germinated_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    taken_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
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
            TIMESTAMP(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when a clone cutting was observed rooted; independent "
                "from when the cutting was taken."
            ),
        ),
    )
    veg_started_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    flower_started_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    culled_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    culled_reason: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    harvested_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    selected_for_breeding_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    selected_for_breeding_reason: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class PlantLocationHistory(SQLModel, table=True):
    __tablename__ = "plant_location_history"
    __table_args__ = (
        CheckConstraint(
            "grid_position IS NULL OR btrim(grid_position) <> ''",
            name="ck_plant_location_grid_position_not_blank",
        ),
        CheckConstraint(
            "end_at IS NULL OR end_at > start_at",
            name="ck_plant_location_time_order",
        ),
        Index(
            "ux_plant_location_current_per_plant",
            "plant_id",
            unique=True,
            postgresql_where=text("end_at IS NULL"),
        ),
        Index(
            "ux_plant_location_current_grid_position_per_tent",
            "tent_id",
            "grid_position",
            unique=True,
            postgresql_where=text("end_at IS NULL AND grid_position IS NOT NULL"),
        ),
        Index(
            "ix_plant_location_current_tent",
            "tent_id",
            "grid_position",
            "plant_id",
            postgresql_where=text("end_at IS NULL"),
        ),
        Index(
            "ix_plant_location_plant_start",
            "plant_id",
            "start_at",
            postgresql_ops={"start_at": "DESC"},
        ),
        ExcludeConstraint(
            ("plant_id", "="),
            (
                text(
                    "tstzrange(start_at, "
                    "COALESCE(end_at, 'infinity'::timestamptz), '[)')"
                ),
                "&&",
            ),
            name="ex_plant_location_no_overlap_per_plant",
            using="gist",
        ),
        ExcludeConstraint(
            ("tent_id", "="),
            ("grid_position", "="),
            (
                text(
                    "tstzrange(start_at, "
                    "COALESCE(end_at, 'infinity'::timestamptz), '[)')"
                ),
                "&&",
            ),
            name="ex_plant_location_no_overlap_per_tent_grid_position",
            using="gist",
            where=text("grid_position IS NOT NULL"),
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    plant_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("plant.id", name="fk_plant_location_plant", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    site_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("site.id", name="fk_plant_location_site", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    tent_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("tent.id", name="fk_plant_location_tent", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    grid_position: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    start_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    end_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    is_current: bool | None = Field(
        default=None,
        sa_column=Column(
            Boolean,
            Computed("end_at IS NULL", persisted=True),
            nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class PlantNote(SQLModel, table=True):
    __tablename__ = "plant_note"
    __table_args__ = (
        CheckConstraint("btrim(body) <> ''", name="ck_plant_note_body_not_blank"),
        CheckConstraint(
            "created_by IS NULL OR btrim(created_by) <> ''",
            name="ck_plant_note_created_by_not_blank",
        ),
        Index(
            "ix_plant_note_plant_observed_at",
            "plant_id",
            "observed_at",
            postgresql_ops={"observed_at": "DESC"},
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    plant_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("plant.id", name="fk_plant_note_plant", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    observed_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_by: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class PlantEvent(SQLModel, table=True):
    __tablename__ = "plant_event"
    __table_args__ = (
        CheckConstraint(
            """
            (CASE WHEN is_pollen_collection THEN 1 ELSE 0 END) +
            (CASE WHEN is_seed_production THEN 1 ELSE 0 END) +
            (CASE WHEN is_clone_taken THEN 1 ELSE 0 END) +
            (CASE WHEN is_sex_observation THEN 1 ELSE 0 END) +
            (CASE WHEN is_reversal THEN 1 ELSE 0 END) +
            (CASE WHEN is_transplant THEN 1 ELSE 0 END) +
            (CASE WHEN is_selection_for_breeding THEN 1 ELSE 0 END) = 1
            """,
            name="ck_plant_event_one_kind",
        ),
        CheckConstraint(
            "reason IS NULL OR btrim(reason) <> ''",
            name="ck_plant_event_reason_not_blank",
        ),
        CheckConstraint(
            "notes IS NULL OR btrim(notes) <> ''",
            name="ck_plant_event_notes_not_blank",
        ),
        CheckConstraint(
            "jsonb_typeof(metadata) = 'object'",
            name="ck_plant_event_metadata_object",
        ),
        Index(
            "ix_plant_event_plant_occurred_at",
            "plant_id",
            "occurred_at",
            postgresql_ops={"occurred_at": "DESC"},
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    plant_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("plant.id", name="fk_plant_event_plant", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    is_pollen_collection: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_seed_production: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_clone_taken: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_sex_observation: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_reversal: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_transplant: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    is_selection_for_breeding: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    occurred_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
        ),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class PlantMetricStream(SQLModel, table=True):
    __tablename__ = "plant_metric_stream"
    __table_args__ = (
        UniqueConstraint(
            "plant_id",
            "capability_id",
            name="uq_plant_metric_stream_plant_capability",
        ),
        Index("ix_plant_metric_stream_plant_id", "plant_id"),
        Index("ix_plant_metric_stream_capability_id", "capability_id"),
        Index("ix_plant_metric_stream_is_active", "is_active"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    plant_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("plant.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    capability_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("capability.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    display_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
