from __future__ import annotations

import pytest

from dirt_hwd.services.thermoforge_protocol import (
    NOTIFY_CHARACTERISTIC_UUID,
    SERVICE_UUID,
    WRITE_CHARACTERISTIC_UUID,
    ThermoForgeStatus,
    build_packet,
    decode_status,
    level_body,
    off_body,
    on_body,
)


@pytest.mark.parametrize(
    ("body", "sequence", "packet_hex"),
    [
        (off_body(), 0x0015, "a50000050015055d0003100101ff00790f"),
        (on_body(), 0x001E, "a5000005001eb4360003100102ff00205f"),
        (level_body(7), 0x0032, "a5000005003251d80003120107ff008f2c"),
        (level_body(1), 0x0045, "a500000500455fa80003120101ff003d8c"),
        (level_body(4), 0x008E, "a5000005008e378f0003120104ff00d67c"),
    ],
)
def test_build_packet_matches_captured_app_writes(
    body: bytes, sequence: int, packet_hex: str
) -> None:
    assert build_packet(body, sequence).hex() == packet_hex


def test_command_bodies() -> None:
    assert off_body().hex() == "0003100101ff00"
    assert on_body().hex() == "0003100102ff00"
    assert level_body(4).hex() == "0003120104ff00"


def test_level_body_rejects_unknown_levels() -> None:
    with pytest.raises(ValueError, match="level"):
        level_body(-1)
    with pytest.raises(ValueError, match="level"):
        level_body(11)


def test_build_packet_rejects_invalid_sequence() -> None:
    with pytest.raises(ValueError, match="sequence"):
        build_packet(off_body(), -1)
    with pytest.raises(ValueError, match="sequence"):
        build_packet(off_body(), 0x10000)


def test_decode_status_from_captured_off_frame() -> None:
    frame = bytes.fromhex(
        "1eff02090730004080008000800000000001f0000000ffff000100000000ffff"
        "000100000000ffff0001000000004650000100000000"
    )

    assert decode_status(frame) == ThermoForgeStatus(
        running=False,
        level=0,
        raw=frame,
    )


def test_decode_status_from_captured_level_4_frame() -> None:
    frame = bytes.fromhex(
        "1eff02090730004080008000800000001202f0000000ffff000100000000ffff"
        "000100000000ffff0001000000004650100100000000"
    )

    assert decode_status(frame) == ThermoForgeStatus(
        running=True,
        level=4,
        raw=frame,
    )


def test_decode_status_ignores_non_status_frames() -> None:
    assert decode_status(bytes.fromhex("a51700048b94172800031200ff0015f2")) is None


def test_ble_uuid_constants() -> None:
    assert SERVICE_UUID == "70d51000-2c7f-4e75-ae8a-d758951ce4e0"
    assert WRITE_CHARACTERISTIC_UUID == "70d51001-2c7f-4e75-ae8a-d758951ce4e0"
    assert NOTIFY_CHARACTERISTIC_UUID == "70d51002-2c7f-4e75-ae8a-d758951ce4e0"
