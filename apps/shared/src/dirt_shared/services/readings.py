"""Sensor reading ingest + query service.

Post-pg-cutover (ADR-006), all timestamp handling is native — no more
``char(58)`` workaround, no more lexical-compare coercion. The bucketed
history queries use ``date_trunc`` and compose cleanly with parametrized
``timestamptz`` bind values.

Legacy location → sensornode_id remains for firmware compatibility, but
canonical reads join ``sensorreading.capability_id`` through device/tent scope
so a second tent can emit the same metric names without contaminating the main
dashboard.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone
from dirt_shared.sensor_contract import LEGACY_LOCATION_DEVICE_IDS, persisted_metrics
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID

# Metrics that get auto-calibrated at ingest (extrema-tracking).
AUTO_CALIBRATED_METRICS = {"soil_moisture_raw"}
# Plausible ADC range — values outside this are noise/spike and skipped.
CAL_CLAMP_MIN = 100.0
CAL_CLAMP_MAX = 3900.0


def compute_calibrated_pct(raw: float, raw_low: float, raw_high: float) -> float | None:
    """Map a raw ADC reading to calibrated percentage via two-point linear.

    raw_low  = wettest ADC seen (100%)
    raw_high = driest ADC seen  (0%)
    Returns None if range is degenerate (raw_high <= raw_low).
    """
    if raw_high <= raw_low:
        return None
    pct = 100.0 * (raw_high - raw) / (raw_high - raw_low)
    return max(0.0, min(100.0, pct))


RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _as_utc(ts: datetime) -> datetime:
    """Attach UTC tzinfo to a naive ``datetime``; pass aware values through.

    Bucket SQL strips tzinfo via ``AT TIME ZONE 'UTC'`` and re-applies it;
    raw ``SensorReading.ts`` columns already come back aware. Contract-
    facing callers require aware datetimes (Pydantic ``AwareDatetime``),
    so normalise both paths here.
    """
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


# Native Postgres bucket expressions. 5-minute buckets for 24h, hourly for
# 7d / 30d. The 1h range returns raw readings (no bucketing).
#
# ``ts AT TIME ZONE 'UTC'`` converts timestamptz to a naive timestamp at
# UTC wall-clock — safe to apply date_trunc + arithmetic against.
#
# ``_BUCKET_SQL`` formats the bucket as a 'Z'-suffixed string for the
# legacy Chart.js payload. ``_BUCKET_SQL_NATIVE`` returns the same
# bucket as ``timestamptz`` so the contract ``get_metric_history`` path
# skips a string↔datetime round-trip.
_BUCKET_SQL = {
    "24h": (
        "SELECT to_char("
        "    date_trunc('hour', ts AT TIME ZONE 'UTC')"
        "    + make_interval(mins => (extract(minute from ts AT TIME ZONE 'UTC')::int / 5) * 5),"  # noqa: E501
        '    \'YYYY-MM-DD"T"HH24:MI:SS"Z"\''
        ") AS bucket, "
        "AVG(value) AS avg_value "
        "FROM sensorreading sr "
        "JOIN capability c ON c.id = sr.capability_id "
        "JOIN device d ON d.id = c.device_id "
        "JOIN site s ON s.id = d.site_id "
        "LEFT JOIN tent t ON t.id = d.tent_id "
        "WHERE sr.ts >= :cutoff AND c.metric_name = :metric "
        "AND s.site_id = :site_id "
        "AND (CAST(:tent_id AS text) IS NULL OR t.tent_id = :tent_id) "
        "AND (CAST(:device_id AS text) IS NULL OR d.device_id = :device_id) "
        "AND (CAST(:capability_public_id AS text) IS NULL OR "
        "c.capability_id = :capability_public_id) "
        "GROUP BY 1 ORDER BY 1"
    ),
    "7d": (
        "SELECT to_char(date_trunc('hour', ts AT TIME ZONE 'UTC'), "
        '\'YYYY-MM-DD"T"HH24:MI:SS"Z"\') AS bucket, '
        "AVG(value) AS avg_value "
        "FROM sensorreading sr "
        "JOIN capability c ON c.id = sr.capability_id "
        "JOIN device d ON d.id = c.device_id "
        "JOIN site s ON s.id = d.site_id "
        "LEFT JOIN tent t ON t.id = d.tent_id "
        "WHERE sr.ts >= :cutoff AND c.metric_name = :metric "
        "AND s.site_id = :site_id "
        "AND (CAST(:tent_id AS text) IS NULL OR t.tent_id = :tent_id) "
        "AND (CAST(:device_id AS text) IS NULL OR d.device_id = :device_id) "
        "AND (CAST(:capability_public_id AS text) IS NULL OR "
        "c.capability_id = :capability_public_id) "
        "GROUP BY 1 ORDER BY 1"
    ),
    "30d": (
        "SELECT to_char(date_trunc('hour', ts AT TIME ZONE 'UTC'), "
        '\'YYYY-MM-DD"T"HH24:MI:SS"Z"\') AS bucket, '
        "AVG(value) AS avg_value "
        "FROM sensorreading sr "
        "JOIN capability c ON c.id = sr.capability_id "
        "JOIN device d ON d.id = c.device_id "
        "JOIN site s ON s.id = d.site_id "
        "LEFT JOIN tent t ON t.id = d.tent_id "
        "WHERE sr.ts >= :cutoff AND c.metric_name = :metric "
        "AND s.site_id = :site_id "
        "AND (CAST(:tent_id AS text) IS NULL OR t.tent_id = :tent_id) "
        "AND (CAST(:device_id AS text) IS NULL OR d.device_id = :device_id) "
        "AND (CAST(:capability_public_id AS text) IS NULL OR "
        "c.capability_id = :capability_public_id) "
        "GROUP BY 1 ORDER BY 1"
    ),
}

# Native-datetime bucket expressions — same math as ``_BUCKET_SQL`` but
# returning ``timestamptz`` (AT TIME ZONE 'UTC' applied only to the
# truncation input; the outer value is re-wrapped to UTC via AT TIME
# ZONE 'UTC' so asyncpg returns an aware datetime).
_BUCKET_SQL_NATIVE = {
    "24h": (
        "SELECT ("
        "    date_trunc('hour', ts AT TIME ZONE 'UTC')"
        "    + make_interval(mins => (extract(minute from ts AT TIME ZONE 'UTC')::int / 5) * 5)"  # noqa: E501
        ") AT TIME ZONE 'UTC' AS bucket, "
        "AVG(value) AS avg_value "
        "FROM sensorreading sr "
        "JOIN capability c ON c.id = sr.capability_id "
        "JOIN device d ON d.id = c.device_id "
        "JOIN site s ON s.id = d.site_id "
        "LEFT JOIN tent t ON t.id = d.tent_id "
        "WHERE sr.ts >= :cutoff AND c.metric_name = :metric "
        "AND s.site_id = :site_id "
        "AND (CAST(:tent_id AS text) IS NULL OR t.tent_id = :tent_id) "
        "AND (CAST(:device_id AS text) IS NULL OR d.device_id = :device_id) "
        "AND (CAST(:capability_public_id AS text) IS NULL OR "
        "c.capability_id = :capability_public_id) "
        "GROUP BY 1 ORDER BY 1"
    ),
    "7d": (
        "SELECT date_trunc('hour', ts AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS bucket, "  # noqa: E501
        "AVG(value) AS avg_value "
        "FROM sensorreading sr "
        "JOIN capability c ON c.id = sr.capability_id "
        "JOIN device d ON d.id = c.device_id "
        "JOIN site s ON s.id = d.site_id "
        "LEFT JOIN tent t ON t.id = d.tent_id "
        "WHERE sr.ts >= :cutoff AND c.metric_name = :metric "
        "AND s.site_id = :site_id "
        "AND (CAST(:tent_id AS text) IS NULL OR t.tent_id = :tent_id) "
        "AND (CAST(:device_id AS text) IS NULL OR d.device_id = :device_id) "
        "AND (CAST(:capability_public_id AS text) IS NULL OR "
        "c.capability_id = :capability_public_id) "
        "GROUP BY 1 ORDER BY 1"
    ),
}


async def _get_metric_series(  # noqa: PLR0913
    session: AsyncSession,
    metric: str,
    range_key: str,
    cutoff: datetime,
    *,
    site_id: str = DEFAULT_SITE_ID,
    tent_id: str | None = DEFAULT_TENT_ID,
    device_id: str | None = None,
    capability_id: str | None = None,
) -> dict[str, list]:
    """Return {labels, values} for a single metric over the given range."""
    params = _history_params(
        cutoff=cutoff,
        metric=metric,
        site_id=site_id,
        tent_id=tent_id,
        device_id=device_id,
        capability_id=capability_id,
    )
    if range_key in _BUCKET_SQL:
        stmt = text(_BUCKET_SQL[range_key])
        result = await session.exec(stmt, params=params)
        rows = result.all()
        return {
            "labels": [r[0] for r in rows],
            "values": [round(float(r[1]), 2) for r in rows],
        }
    # Raw readings (1h) — no bucketing.
    result = await session.exec(
        _scoped_readings_select(
            metric,
            site_id=site_id,
            tent_id=tent_id,
            device_id=device_id,
            capability_id=capability_id,
        )
        .where(SensorReading.ts >= cutoff)
        .order_by(SensorReading.ts)
    )
    rows = result.all()
    return {
        "labels": [r.ts.isoformat() for r in rows],
        "values": [round(r.value, 2) for r in rows],
    }


async def _get_sensornode_id(
    session: AsyncSession, location: SensorLocation | str
) -> int | None:
    """Look up a sensornode surrogate id by its location enum value."""
    result = await session.exec(
        select(SensorNode.id).where(SensorNode.location == location)
    )
    return result.first()


def _legacy_device_id(location: SensorLocation | str | None) -> str | None:
    if location is None:
        return None
    try:
        loc = (
            location
            if isinstance(location, SensorLocation)
            else SensorLocation(location)
        )
    except ValueError:
        return None
    return LEGACY_LOCATION_DEVICE_IDS.get(loc)


def _history_params(  # noqa: PLR0913
    *,
    cutoff: datetime,
    metric: str,
    site_id: str,
    tent_id: str | None,
    device_id: str | None,
    capability_id: str | None,
) -> dict[str, object]:
    return {
        "cutoff": cutoff,
        "metric": metric,
        "site_id": site_id,
        "tent_id": tent_id,
        "device_id": device_id,
        "capability_public_id": capability_id,
    }


def _scoped_readings_select(  # noqa: PLR0913
    metric: str,
    *,
    site_id: str = DEFAULT_SITE_ID,
    tent_id: str | None = DEFAULT_TENT_ID,
    zone_id: str | None = None,
    device_id: str | None = None,
    capability_id: str | None = None,
):
    stmt = (
        select(SensorReading)
        .join(Capability, Capability.id == SensorReading.capability_id)
        .join(Device, Device.id == Capability.device_id)
        .join(Site, Site.id == Device.site_id)
        .where(Site.site_id == site_id)
        .where(Capability.metric_name == metric)
    )
    if tent_id is not None:
        stmt = stmt.join(Tent, Tent.id == Device.tent_id).where(Tent.tent_id == tent_id)
    if zone_id is not None:
        stmt = stmt.join(Zone, Zone.id == Device.zone_id).where(Zone.zone_id == zone_id)
    if device_id is not None:
        stmt = stmt.where(Device.device_id == device_id)
    if capability_id is not None:
        stmt = stmt.where(Capability.capability_id == capability_id)
    return stmt


async def _resolve_capability_ids(  # noqa: PLR0913
    session: AsyncSession,
    *,
    metric_names: Iterable[str],
    location: SensorLocation | str | None,
    site_id: str,
    tent_id: str | None,
    zone_id: str | None,
    device_id: str | None,
    capability_id: str | None,
) -> dict[str, int]:
    resolved_device_id = device_id or _legacy_device_id(location)
    if resolved_device_id is None:
        return {}

    stmt = (
        select(Capability.metric_name, Capability.id)
        .join(Device, Device.id == Capability.device_id)
        .join(Site, Site.id == Device.site_id)
        .where(Site.site_id == site_id)
        .where(Device.device_id == resolved_device_id)
        .where(Capability.metric_name.in_(set(metric_names)))
    )
    if tent_id is not None:
        stmt = stmt.join(Tent, Tent.id == Device.tent_id).where(Tent.tent_id == tent_id)
    if zone_id is not None:
        stmt = stmt.join(Zone, Zone.id == Device.zone_id).where(Zone.zone_id == zone_id)
    if capability_id is not None:
        stmt = stmt.where(Capability.capability_id == capability_id)

    rows = (await session.exec(stmt)).all()
    return {metric_name: cap_id for metric_name, cap_id in rows if metric_name}


async def resolve_metric_capability_id(  # noqa: PLR0913
    session: AsyncSession,
    *,
    metric: str,
    location: SensorLocation | str | None = None,
    site_id: str = DEFAULT_SITE_ID,
    tent_id: str | None = DEFAULT_TENT_ID,
    zone_id: str | None = None,
    device_id: str | None = None,
    capability_id: str | None = None,
) -> int | None:
    """Resolve one public metric/scope tuple to the canonical capability PK."""
    matches = await _resolve_capability_ids(
        session,
        metric_names=(metric,),
        location=location,
        site_id=site_id,
        tent_id=tent_id,
        zone_id=zone_id,
        device_id=device_id,
        capability_id=capability_id,
    )
    return matches.get(metric)


async def get_sensor_calibration(
    session: AsyncSession,
    *,
    sensornode_id: int | None,
    metric: str,
    capability_id: int | None = None,
) -> SensorCalibration | None:
    """Return calibration by scoped capability first, then legacy node/metric."""
    if capability_id is not None:
        result = await session.exec(
            select(SensorCalibration)
            .where(SensorCalibration.capability_id == capability_id)
            .where(SensorCalibration.metric == metric)
        )
        cal = result.first()
        if cal is not None:
            return cal

    if sensornode_id is not None:
        result = await session.exec(
            select(SensorCalibration)
            .where(SensorCalibration.sensornode_id == sensornode_id)
            .where(SensorCalibration.metric == metric)
        )
        return result.first()
    return None


async def _update_calibration(
    session: AsyncSession,
    sensornode_id: int,
    metric: str,
    value: float,
    *,
    capability_id: int | None = None,
) -> None:
    """Widen the scoped calibration range if ``value`` is a new extremum."""
    cal = await get_sensor_calibration(
        session,
        sensornode_id=sensornode_id,
        metric=metric,
        capability_id=capability_id,
    )
    if cal is None:
        session.add(
            SensorCalibration(
                sensornode_id=sensornode_id,
                capability_id=capability_id,
                metric=metric,
                raw_low=value,
                raw_high=value,
            )
        )
    else:
        if value < cal.raw_low:
            cal.raw_low = value
        if value > cal.raw_high:
            cal.raw_high = value


class ReadingsService:
    """Sensor reading ingest + query. Constructor-inject the engine.

    Wired into FastAPI via ``app.state.readings`` in
    ``dirt_web.app.create_app``; resolved by the ``get_readings``
    provider in ``dirt_web.deps``.

    The clock is constructor-injected so ingest stamps and history
    cutoffs are deterministic in tests.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    def now(self) -> datetime:
        """UTC ``datetime`` from the injected clock — test seam.

        Endpoints composing a readings-plus-extras envelope (``/api/sensors/current``
        fills in mock fan / reservoir values when the DB is cold) use this so
        the only source of "what time is it" in the service layer is the
        shared injected clock. Avoids a second concrete ``datetime.now()``
        call in the route handler — see
        ``apps/tests/invariants/test_no_concrete_clock_in_production.py``.
        """
        return self._clock()

    async def get_latest_reading(  # noqa: PLR0913
        self,
        metric: str,
        location: SensorLocation | str = SensorLocation.TENT,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str | None = DEFAULT_TENT_ID,
        zone_id: str | None = None,
        device_id: str | None = None,
        capability_id: str | None = None,
    ) -> SensorReading | None:
        """Return the most recent scoped reading for ``metric``.

        ``location`` remains as legacy firmware/API shorthand. The canonical
        read path resolves it to a device/capability under ``site_id`` and
        ``tent_id``.
        """
        async with AsyncSession(self._engine) as session:
            resolved_device_id = device_id
            if resolved_device_id is None and tent_id == DEFAULT_TENT_ID:
                resolved_device_id = _legacy_device_id(location)
            result = await session.exec(
                _scoped_readings_select(
                    metric,
                    site_id=site_id,
                    tent_id=tent_id,
                    zone_id=zone_id,
                    device_id=resolved_device_id,
                    capability_id=capability_id,
                )
                .order_by(SensorReading.ts.desc())
                .limit(1)
            )
            return result.first()

    async def get_metric_freshness_snapshot(
        self,
        stale_cutoff: datetime,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str | None = None,
    ) -> dict[tuple[SensorLocation, str], tuple[str, datetime | None]]:
        """For every metric in ``PERSISTED_METRICS``, classify as fresh/stale.

        Returns ``{(location, metric): ("fresh"|"stale", last_ts_or_None)}``.

        Skips locations whose sensornode last_seen is older than
        ``stale_cutoff`` — whole-node outages are DeviceWatchdog's job, and
        a dead node would otherwise fan out into N alerts.
        """
        from dirt_shared.sensor_contract import PERSISTED_METRICS

        out: dict[tuple[SensorLocation, str], tuple[str, datetime | None]] = {}
        async with AsyncSession(self._engine) as session:
            nodes = (await session.exec(select(SensorNode))).all()
            by_loc: dict[SensorLocation, SensorNode] = {n.location: n for n in nodes}

            for location, metrics in PERSISTED_METRICS.items():
                if not metrics:
                    continue
                node = by_loc.get(location)
                if node is None or node.id is None or node.last_seen is None:
                    continue
                if _as_utc(node.last_seen) < stale_cutoff:
                    continue

                device_id = _legacy_device_id(location)
                for metric in sorted(metrics):
                    row = (
                        await session.exec(
                            _scoped_readings_select(
                                metric,
                                site_id=site_id,
                                tent_id=tent_id,
                                device_id=device_id,
                            )
                            .order_by(SensorReading.ts.desc())
                            .limit(1)
                        )
                    ).first()
                    if row is None:
                        out[(location, metric)] = ("stale", None)
                        continue
                    ts = _as_utc(row.ts)
                    status = "fresh" if ts >= stale_cutoff else "stale"
                    out[(location, metric)] = (status, ts)
        return out

    async def get_capability_freshness_snapshot(
        self,
        stale_cutoff: datetime,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str | None = DEFAULT_TENT_ID,
    ) -> dict[str, tuple[str, datetime | None, dict[str, str | None]]]:
        """Classify freshness keyed by stable capability id for alert state."""
        from dirt_shared.sensor_contract import PERSISTED_METRICS

        out: dict[str, tuple[str, datetime | None, dict[str, str | None]]] = {}
        async with AsyncSession(self._engine) as session:
            nodes = (await session.exec(select(SensorNode))).all()
            by_loc: dict[SensorLocation, SensorNode] = {n.location: n for n in nodes}

            for location, metrics in PERSISTED_METRICS.items():
                node = by_loc.get(location)
                if node is None or node.last_seen is None:
                    continue
                if _as_utc(node.last_seen) < stale_cutoff:
                    continue

                device_public_id = _legacy_device_id(location)
                if device_public_id is None:
                    continue

                for metric in sorted(metrics):
                    capability_pk = await resolve_metric_capability_id(
                        session,
                        metric=metric,
                        location=location,
                        site_id=site_id,
                        tent_id=tent_id,
                        device_id=device_public_id,
                    )
                    if capability_pk is None:
                        continue
                    cap_row = (
                        await session.exec(
                            select(Capability.capability_id, Device.device_id)
                            .join(Device, Device.id == Capability.device_id)
                            .where(Capability.id == capability_pk)
                        )
                    ).first()
                    if cap_row is None:
                        continue
                    capability_public_id, resolved_device_id = cap_row
                    row = (
                        await session.exec(
                            _scoped_readings_select(
                                metric,
                                site_id=site_id,
                                tent_id=tent_id,
                                device_id=resolved_device_id,
                                capability_id=capability_public_id,
                            )
                            .order_by(SensorReading.ts.desc())
                            .limit(1)
                        )
                    ).first()
                    last_seen = None if row is None else _as_utc(row.ts)
                    status = (
                        "stale"
                        if last_seen is None or last_seen < stale_cutoff
                        else "fresh"
                    )
                    out[capability_public_id] = (
                        status,
                        last_seen,
                        {
                            "site_id": site_id,
                            "tent_id": tent_id,
                            "device_id": resolved_device_id,
                            "capability_id": capability_public_id,
                            "location": location.value,
                            "metric": metric,
                        },
                    )
        return out

    async def is_sensor_stale(self, threshold: int = 10) -> bool:
        """Return True if the last ``threshold`` tent temperature readings are identical."""  # noqa: E501
        async with AsyncSession(self._engine) as session:
            node_id = await _get_sensornode_id(session, SensorLocation.TENT)
            if node_id is None:
                return False
            result = await session.exec(
                select(SensorReading)
                .where(SensorReading.sensornode_id == node_id)
                .where(SensorReading.metric == "temperature_f")
                .order_by(SensorReading.ts.desc())
                .limit(threshold)
            )
            rows = result.all()
        if len(rows) < threshold:
            return False
        return len({r.value for r in rows}) == 1

    async def ingest_reading(  # noqa: PLR0913 — location+metrics are the reading; ip/firmware/uptime are optional node-metadata upserts bundled into the same transaction by design.
        self,
        location: SensorLocation | str,
        metrics: dict[str, float],
        source: SensorSource | str = SensorSource.ESP32,
        ip: str | None = None,
        firmware_version: str | None = None,
        uptime_ms: int | None = None,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str | None = DEFAULT_TENT_ID,
        zone_id: str | None = None,
        device_id: str | None = None,
        capability_id: str | None = None,
    ) -> None:
        """Record a batch of sensor readings and upsert node metadata."""
        now = self._clock()
        async with AsyncSession(self._engine) as session:
            # Step 1 — find-or-upsert the sensornode and flush to get its id.
            node = (
                await session.exec(
                    select(SensorNode).where(SensorNode.location == location)
                )
            ).first()
            if node is None:
                # Shouldn't happen post-seed — but if someone widens the enum
                # and forgets to seed, create rather than fail.
                node = SensorNode(location=location)
            # Only overwrite identity fields when the caller provided them.
            # Internal callers (e.g. the humidifier loop recording its own
            # on/off state) pass None for ip/firmware/uptime; don't null out
            # the metadata the ESP32 ingest path populates for other nodes.
            if ip is not None:
                node.ip = ip
            if firmware_version is not None:
                node.firmware_version = firmware_version
            if uptime_ms is not None:
                node.uptime_ms = uptime_ms
            node.last_seen = now
            session.add(node)
            await session.flush()  # populate node.id for the FK on SensorReading
            assert node.id is not None  # noqa: S101 (type narrow: post-flush)

            capability_ids = await _resolve_capability_ids(
                session,
                metric_names=metrics.keys(),
                location=location,
                site_id=site_id,
                tent_id=tent_id,
                zone_id=zone_id,
                device_id=device_id,
                capability_id=capability_id if len(metrics) == 1 else None,
            )

            # Step 2 + 3 — readings and (optional) calibration updates.
            for metric_name, value in metrics.items():
                session.add(
                    SensorReading(
                        ts=now,
                        sensornode_id=node.id,
                        capability_id=capability_ids.get(metric_name),
                        metric=metric_name,
                        value=value,
                        source=source,
                    )
                )
                if (
                    metric_name in AUTO_CALIBRATED_METRICS
                    and CAL_CLAMP_MIN <= value <= CAL_CLAMP_MAX
                ):
                    await _update_calibration(
                        session,
                        node.id,
                        metric_name,
                        value,
                        capability_id=capability_ids.get(metric_name),
                    )

            await session.commit()

    async def touch_node(
        self,
        location: SensorLocation | str,
        *,
        ip: str | None = None,
        firmware_version: str | None = None,
        uptime_ms: int | None = None,
    ) -> None:
        """Update node heartbeat metadata without writing sensor readings."""
        now = self._clock()
        async with AsyncSession(self._engine) as session:
            node = (
                await session.exec(
                    select(SensorNode).where(SensorNode.location == location)
                )
            ).first()
            if node is None:
                node = SensorNode(location=location)
            if ip is not None:
                node.ip = ip
            if firmware_version is not None:
                node.firmware_version = firmware_version
            if uptime_ms is not None:
                node.uptime_ms = uptime_ms
            node.last_seen = now
            session.add(node)
            await session.commit()

    async def get_sensor_history(self, range_key: str) -> dict[str, dict[str, list]]:
        """Return all metrics over the given range, batched."""
        delta = RANGE_DELTAS[range_key]
        cutoff = self._clock() - delta

        async with AsyncSession(self._engine) as session:
            return {
                metric: await _get_metric_series(session, metric, range_key, cutoff)
                for metric in sorted(persisted_metrics(SensorLocation.TENT))
            }

    async def get_metric_history(  # noqa: PLR0913
        self,
        metric: str,
        range_key: str,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str | None = DEFAULT_TENT_ID,
        zone_id: str | None = None,
        device_id: str | None = None,
        capability_id: str | None = None,
    ) -> list[tuple[datetime, float]]:
        """Return bucketed ``(ts, value)`` points for one DB-backed metric.

        Raw mode for ``range_key='1h'``; 5-min buckets for ``24h``; hourly
        for ``7d``. Returns aware UTC ``datetime``s straight from Postgres
        so the contract endpoint can hand them to ``HistoryPoint``
        without a str-format round-trip.

        Filters by capability/device scope, not just metric name, so a
        second tent can emit ``temperature_f`` without appearing in the
        default main dashboard history.
        """
        delta = RANGE_DELTAS[range_key]
        cutoff = self._clock() - delta
        async with AsyncSession(self._engine) as session:
            params = _history_params(
                cutoff=cutoff,
                metric=metric,
                site_id=site_id,
                tent_id=tent_id,
                device_id=device_id,
                capability_id=capability_id,
            )
            if range_key in _BUCKET_SQL_NATIVE:
                stmt = text(_BUCKET_SQL_NATIVE[range_key])
                result = await session.exec(stmt, params=params)
                return [
                    (_as_utc(ts), round(float(value), 2)) for ts, value in result.all()
                ]
            # Raw readings (1h) — no bucketing.
            result = await session.exec(
                _scoped_readings_select(
                    metric,
                    site_id=site_id,
                    tent_id=tent_id,
                    zone_id=zone_id,
                    device_id=device_id,
                    capability_id=capability_id,
                )
                .where(SensorReading.ts >= cutoff)
                .order_by(SensorReading.ts)
            )
            return [
                (_as_utc(row.ts), round(float(row.value), 2)) for row in result.all()
            ]
