from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import datetime

from dirt_hwd.tools.substrate_calibration.schemas import (
    FORMULA_TEMPLATE,
    AnchorType,
    CalibrationSession,
    CalibrationSummary,
    Capture,
    CaptureStats,
    MetricStats,
    ProbeCalibrationSummary,
    ProbeIdentity,
    ProbeSample,
)

LOW_SAMPLE_COUNT = 10
MIN_MOISTURE_SPAN = 5.0


def _metric_stats(values: Iterable[float | None]) -> MetricStats:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return MetricStats(count=0)
    return MetricStats(
        count=len(valid),
        mean=statistics.fmean(valid),
        min=min(valid),
        max=max(valid),
        stddev=statistics.pstdev(valid) if len(valid) > 1 else 0.0,
    )


def compute_capture_stats(samples: list[ProbeSample]) -> CaptureStats:
    valid_samples = [sample for sample in samples if sample.valid]
    return CaptureStats(
        sample_count=len(samples),
        valid_sample_count=len(valid_samples),
        soil_moisture_pct=_metric_stats(
            sample.soil_moisture_pct for sample in valid_samples
        ),
        substrate_ec_us_cm=_metric_stats(
            sample.substrate_ec_us_cm for sample in valid_samples
        ),
        substrate_ph=_metric_stats(sample.substrate_ph for sample in valid_samples),
        substrate_temp_c=_metric_stats(
            sample.substrate_temp_c for sample in valid_samples
        ),
    )


def _capture_moisture_values(capture: Capture) -> list[float]:
    return [
        sample.soil_moisture_pct
        for sample in capture.samples
        if sample.valid and sample.soil_moisture_pct is not None
    ]


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _formula(dry_anchor_mean: float, span: float) -> str:
    return f"100 * (raw_moisture_pct - {dry_anchor_mean:.3f}) / {span:.3f}"


def _probe_summary(
    probe: ProbeIdentity,
    captures: list[Capture],
) -> ProbeCalibrationSummary:
    dry_captures = [
        capture
        for capture in captures
        if capture.probe_id == probe.probe_id and capture.anchor_type == AnchorType.DRY
    ]
    wet_captures = [
        capture
        for capture in captures
        if capture.probe_id == probe.probe_id
        and capture.anchor_type == AnchorType.WET_CAPACITY
    ]
    dry_values = [
        value for capture in dry_captures for value in _capture_moisture_values(capture)
    ]
    wet_values = [
        value for capture in wet_captures for value in _capture_moisture_values(capture)
    ]
    dry_anchor_mean = _mean(dry_values)
    wet_anchor_mean = _mean(wet_values)
    span = (
        wet_anchor_mean - dry_anchor_mean
        if dry_anchor_mean is not None and wet_anchor_mean is not None
        else None
    )

    warnings: list[str] = []
    if not dry_values:
        warnings.append("missing dry anchor")
    if not wet_values:
        warnings.append("missing wet_capacity anchor")
    for capture in dry_captures + wet_captures:
        moisture_count = capture.stats.soil_moisture_pct.count
        if moisture_count < LOW_SAMPLE_COUNT:
            warnings.append(
                f"capture {capture.id} has low moisture sample count "
                f"({moisture_count} < {LOW_SAMPLE_COUNT})"
            )

    formula: str | None = None
    ready = False
    if span is not None:
        if span <= 0:
            warnings.append("dry anchor mean is not below wet_capacity anchor mean")
        elif span < MIN_MOISTURE_SPAN:
            warnings.append(
                f"moisture anchor span {span:.3f} is below {MIN_MOISTURE_SPAN:.3f}"
            )
        else:
            formula = _formula(dry_anchor_mean, span)
            ready = True

    return ProbeCalibrationSummary(
        probe=probe,
        dry_anchor_mean=dry_anchor_mean,
        wet_anchor_mean=wet_anchor_mean,
        span=span,
        dry_capture_count=len(dry_captures),
        wet_capture_count=len(wet_captures),
        valid_dry_sample_count=len(dry_values),
        valid_wet_sample_count=len(wet_values),
        formula_template=FORMULA_TEMPLATE,
        formula=formula,
        ready=ready,
        warnings=warnings,
    )


def summarize_session(
    session: CalibrationSession,
    *,
    completed_at: datetime | None = None,
) -> CalibrationSummary:
    captures = session.accepted_captures
    probe_map = {probe.probe_id: probe for probe in session.probe_map}
    for capture in captures:
        if capture.probe_id not in probe_map:
            probe_map[capture.probe_id] = ProbeIdentity(
                probe_id=capture.probe_id,
                modbus_address=capture.modbus_address,
                device_id=capture.device_id,
            )

    probe_summaries = [
        _probe_summary(probe, captures)
        for probe in sorted(probe_map.values(), key=lambda item: item.probe_id)
    ]
    warnings = [
        f"probe {summary.probe.probe_id}: {warning}"
        for summary in probe_summaries
        for warning in summary.warnings
    ]
    return CalibrationSummary(
        formula_template=FORMULA_TEMPLATE,
        probes=probe_summaries,
        warnings=warnings,
        completed_at=completed_at,
    )
