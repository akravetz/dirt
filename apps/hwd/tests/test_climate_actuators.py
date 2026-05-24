from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.climate_actuators import (
    DEFAULT_DEHUMIDIFIER_DEVICE_ID,
    ClimateKasaPlugTarget,
    FanNodeActuator,
    H7142HumidifierActuator,
    KasaDehumidifierActuator,
    ThermoForgeActuatorDevice,
    ThermoForgeHeaterActuator,
    ThermoForgeHeaterTarget,
    load_dehumidifier_target,
)
from dirt_hwd.services.kasa_inventory import (
    KasaExpectedDevice,
    KasaObservation,
    KasaVerifiedDevice,
)
from dirt_hwd.services.thermoforge_ble import ThermoForgeTarget
from dirt_hwd.services.thermoforge_protocol import ThermoForgeStatus
from dirt_shared.config import HumidifierConfig, ScheduledKasaConfig
from dirt_shared.models import Capability, SensorReading
from dirt_shared.services.govee import WORKMODE_MANUAL, StateSnapshot
from dirt_shared.services.readings import ReadingsService


class FakeFanClient:
    def __init__(self) -> None:
        self.duty: int = 20

    async def get_state(self) -> dict[str, int]:
        return {"set_duty_pct": self.duty, "reported_duty_pct": self.duty}

    async def set_duty(self, duty_pct: int) -> int:
        self.duty = duty_pct
        return duty_pct


class FakeH7142Client:
    def __init__(self, snapshot: StateSnapshot) -> None:
        self.snapshot = snapshot
        self.calls: list[tuple[str, object]] = []

    async def get_state(self, sku: str, mac: str) -> StateSnapshot:
        self.calls.append(("get_state", (sku, mac)))
        return self.snapshot

    async def set_power(self, sku: str, mac: str, *, on: bool) -> None:
        self.calls.append(("set_power", (sku, mac, on)))

    async def set_manual_level(self, sku: str, mac: str, level: int) -> None:
        self.calls.append(("set_manual_level", (sku, mac, level)))


class FakePlug:
    def __init__(self, *, is_on: bool = False) -> None:
        self.is_on = is_on
        self.update_calls = 0
        self.turn_on_calls = 0
        self.turn_off_calls = 0
        self.disconnect_calls = 0

    async def update(self) -> None:
        self.update_calls += 1

    async def turn_on(self) -> None:
        self.turn_on_calls += 1
        self.is_on = True

    async def turn_off(self) -> None:
        self.turn_off_calls += 1
        self.is_on = False

    async def disconnect(self) -> None:
        self.disconnect_calls += 1


class FakeKasaInventory:
    def __init__(self, plug: FakePlug) -> None:
        self.plug = plug
        self.expected: list[KasaExpectedDevice] = []

    async def connect_verified(
        self,
        expected: KasaExpectedDevice,
    ) -> KasaVerifiedDevice:
        self.expected.append(expected)
        return KasaVerifiedDevice(
            device=self.plug,
            observation=KasaObservation(
                host=expected.host,
                mac=expected.mac,
                alias="tent-dehumidifier",
                model="EP10",
                hardware_version="1.0",
                firmware_version="1.1.1",
                rssi=-55,
            ),
        )


class FakeThermoForgeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []
        self.status = ThermoForgeStatus(running=False, level=0)

    async def connect(self) -> ThermoForgeStatus:
        self.calls.append(("connect", None))
        return self.status

    async def disconnect(self) -> None:
        self.calls.append(("disconnect", None))

    async def reconcile(self, target: ThermoForgeTarget) -> ThermoForgeStatus:
        self.calls.append(("reconcile", target))
        self.status = ThermoForgeStatus(
            running=target.running,
            level=target.level if target.running else 0,
        )
        return self.status


class FakeReadings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def ingest_reading(
        self,
        metrics: dict[str, float],
        **kwargs: object,
    ) -> int:
        self.calls.append({"metrics": metrics, **kwargs})
        return len(metrics)


def _humidifier_config() -> HumidifierConfig:
    return HumidifierConfig(
        govee_api_key="test-key",
        govee_sku="H7142",
        govee_mac="AA:BB:CC:DD:EE:FF",
        mist_levels=9,
        level_hysteresis_pct=3.0,
        pi_kc=1.0,
        pi_ki=0.1,
        pi_integrator_clamp=100.0,
        pi_threshold_pct=5.0,
        pi_threshold_hysteresis_pct=2.0,
        pi_night_offset_kpa=0.0,
        lights_off_prep_minutes=5,
        poll_interval=30,
        failsafe_stale_seconds=300,
        ineffective_alert_after_s=900.0,
        ineffective_min_vpd_drop_kpa=0.05,
        telegram_bot_token="",
        telegram_chat_id="",
    )


def _kasa_config() -> ScheduledKasaConfig:
    return ScheduledKasaConfig(
        kasa_username="user",
        kasa_password="pass",
        discovery_target="255.255.255.255",
        poll_interval=30,
    )


async def test_fan_node_actuator_reads_and_sets_duty() -> None:
    client = FakeFanClient()
    actuator = FanNodeActuator(client)  # type: ignore[arg-type]

    assert await actuator.read_duty() == 20
    assert await actuator.set_duty(47) == 47
    assert await actuator.read_duty() == 47


async def test_h7142_humidifier_actuator_uses_quantizer_and_dispatch_plan() -> None:
    readings = FakeReadings()
    client = FakeH7142Client(
        StateSnapshot(
            online=True,
            power_on=False,
            work_mode=WORKMODE_MANUAL,
            mode_value=1,
            lack_water=False,
        )
    )
    actuator = H7142HumidifierActuator(
        _humidifier_config(),
        client,
        readings=readings,
        interleave_s=0.0,
    )

    output = await actuator.set_intensity(42.0)

    assert output.target_level == 4
    assert client.calls == [
        ("get_state", ("H7142", "AA:BB:CC:DD:EE:FF")),
        ("set_power", ("H7142", "AA:BB:CC:DD:EE:FF", True)),
        ("set_manual_level", ("H7142", "AA:BB:CC:DD:EE:FF", 4)),
    ]
    assert readings.calls == [
        {
            "metrics": {"humidifier_on": 1.0, "humidifier_mist_level": 4.0},
            "source": "govee",
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "canopy",
            "device_id": "govee-h7142-main",
        }
    ]


async def test_load_dehumidifier_target_uses_db_known_natural_id(app_engine) -> None:
    target = await load_dehumidifier_target(app_engine)

    assert target == ClimateKasaPlugTarget(
        site_id="homebox",
        tent_id="main",
        zone_id="canopy",
        device_id=DEFAULT_DEHUMIDIFIER_DEVICE_ID,
        capability_id="power",
        host="192.168.1.208",
        provider_uid="58:04:4F:10:3D:19",
    )


async def test_kasa_dehumidifier_actuator_sets_power_and_records_reading(
    app_engine,
) -> None:
    plug = FakePlug(is_on=False)
    inventory = FakeKasaInventory(plug)
    actuator = KasaDehumidifierActuator(
        _kasa_config(),
        engine=app_engine,
        readings=ReadingsService(
            app_engine,
            clock=lambda: datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        ),
        inventory=inventory,
    )

    assert await actuator.set_power(True) is True

    assert plug.update_calls == 1
    assert plug.turn_on_calls == 1
    assert plug.turn_off_calls == 0
    assert plug.disconnect_calls == 1
    assert inventory.expected == [
        KasaExpectedDevice(
            device_id=DEFAULT_DEHUMIDIFIER_DEVICE_ID,
            mac="58:04:4F:10:3D:19",
            host="192.168.1.208",
        )
    ]
    async with AsyncSession(app_engine) as session:
        reading = (
            await session.exec(
                select(SensorReading)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .where(Capability.metric_name == "dehumidifier_on")
            )
        ).one()
    assert reading.value == 1.0
    assert reading.source == "kasa"


def test_thermoforge_heater_target_validates_staged_levels() -> None:
    assert ThermoForgeHeaterTarget.off().level == 0
    assert ThermoForgeHeaterTarget.heat_level(1).level == 1
    assert ThermoForgeHeaterTarget.heat_level(10).level == 10

    for unsupported in (-1, 11):
        with pytest.raises(ValueError, match=r"off or level 1\.\.10"):
            ThermoForgeHeaterTarget(unsupported)
    with pytest.raises(ValueError, match="active ThermoForge heat level"):
        ThermoForgeHeaterTarget.heat_level(0)


async def test_thermoforge_heater_actuator_reconciles_and_records_reading() -> None:
    client = FakeThermoForgeClient()
    readings = FakeReadings()
    device = ThermoForgeActuatorDevice(
        site_id="homebox",
        tent_id="main",
        zone_id="canopy",
        device_id="ac-infinity-thermoforge-main",
        capability_id="heat",
        provider_uid="80:B5:4E:4D:27:01",
    )
    actuator = ThermoForgeHeaterActuator(
        device,
        client_factory=lambda mac: client,
        readings=readings,
    )

    status = await actuator.set_target(ThermoForgeHeaterTarget.heat_level(4))

    assert status == ThermoForgeStatus(running=True, level=4)
    assert client.calls == [
        ("connect", None),
        ("reconcile", ThermoForgeTarget(running=True, level=4)),
        ("disconnect", None),
    ]
    assert readings.calls == [
        {
            "metrics": {"heater_on": 1.0, "heater_heat_level": 4.0},
            "device_id": "ac-infinity-thermoforge-main",
            "source": "ac_infinity",
            "site_id": "homebox",
            "tent_id": "main",
            "zone_id": "canopy",
            "capability_id": "heat",
        }
    ]
