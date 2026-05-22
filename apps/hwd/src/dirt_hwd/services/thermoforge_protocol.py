"""Pure AC Infinity ThermoForge BLE protocol helpers."""

from __future__ import annotations

from dataclasses import dataclass

from crccheck.crc import Crc16CcittFalse

SERVICE_UUID = "70d51000-2c7f-4e75-ae8a-d758951ce4e0"
WRITE_CHARACTERISTIC_UUID = "70d51001-2c7f-4e75-ae8a-d758951ce4e0"
NOTIFY_CHARACTERISTIC_UUID = "70d51002-2c7f-4e75-ae8a-d758951ce4e0"

OFF_BODY = bytes.fromhex("0003100101ff00")
ON_BODY = bytes.fromhex("0003100102ff00")

STATUS_FRAME_LENGTH = 54
RUNNING_FLAGS_INDEX = 16
RUNNING_STATE_INDEX = 17
LEVEL_INDEX = 48


@dataclass(frozen=True, slots=True)
class ThermoForgeStatus:
    running: bool
    level: int
    raw: bytes | None = None


def off_body() -> bytes:
    return OFF_BODY


def on_body() -> bytes:
    return ON_BODY


def level_body(level: int) -> bytes:
    if not 0 <= level <= 10:
        raise ValueError("level must be between 0 and 10")
    return bytes.fromhex("00031201") + bytes([level]) + bytes.fromhex("ff00")


def build_packet(body: bytes, sequence: int) -> bytes:
    if not 0 <= sequence <= 0xFFFF:
        raise ValueError("sequence must fit in 16 bits")
    if len(body) < 2:
        raise ValueError("body must be at least 2 bytes")

    prefix = b"\xa5\x00" + (len(body) - 2).to_bytes(2, "big")
    prefix += sequence.to_bytes(2, "big")
    return prefix + _crc16(prefix) + body + _crc16(body)


def decode_status(frame: bytes) -> ThermoForgeStatus | None:
    if len(frame) != STATUS_FRAME_LENGTH:
        return None

    running = frame[RUNNING_STATE_INDEX] == 0x02 and bool(
        frame[RUNNING_FLAGS_INDEX] & 0x02
    )
    level = (frame[LEVEL_INDEX] & 0x3C) >> 2
    return ThermoForgeStatus(running=running, level=level, raw=frame)


def _crc16(data: bytes) -> bytes:
    return Crc16CcittFalse.calc(data).to_bytes(2, "big")
