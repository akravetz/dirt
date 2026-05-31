"""Backend-owned dashboard metric presentation registry."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Double, Integer, Text, text
from sqlmodel import Field, SQLModel


class MetricPresentation(SQLModel, table=True):
    __tablename__ = "metric_presentation"

    metric: str = Field(sa_column=Column(Text, primary_key=True))
    display_name: str = Field(sa_column=Column(Text, nullable=False))
    unit: str = Field(sa_column=Column(Text, nullable=False))
    accent: str = Field(sa_column=Column(Text, nullable=False))
    value_precision: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default=text("1")),
    )
    y_min: float | None = Field(default=None, sa_column=Column(Double, nullable=True))
    y_max: float | None = Field(default=None, sa_column=Column(Double, nullable=True))
    current_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    history_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    dashboard_group: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    dashboard_group_label: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    dashboard_group_order: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    display_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
