from sqlmodel import Field, SQLModel


class SensorCalibration(SQLModel, table=True):
    """Per-(location, metric) two-point linear calibration.

    Auto-calibrated at ingest time: raw_low is the wettest reading ever seen,
    raw_high is the driest. Only created for metrics in the auto-calibrated
    set (currently {"soil_moisture_raw"}). No row = no calibration known.

    Derivation of calibrated percentage from raw:
        pct = 100 * (raw_high - raw) / (raw_high - raw_low)
    clamped to [0, 100]. Returns None if raw_high <= raw_low (degenerate,
    e.g., only one reading ever received).
    """

    location: str = Field(primary_key=True)
    metric: str = Field(primary_key=True)
    raw_low: float  # wettest ADC value seen (→ 100%)
    raw_high: float  # driest ADC value seen  (→ 0%)
