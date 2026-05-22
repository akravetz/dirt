from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "scripts" / "telegram-alert"
    loader = importlib.machinery.SourceFileLoader("telegram_alert_script", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class _Response:
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok":true}'


def test_service_alert_cooldown_suppresses_repeat_send(
    tmp_path: Path,
    monkeypatch,
) -> None:
    script = _load_script()
    state_path = tmp_path / "state.json"
    sent: list[bytes] = []
    now = 1000.0

    def fake_time() -> float:
        return now

    def fake_urlopen(_url: str, *, data: bytes, timeout: float) -> _Response:
        assert timeout == 10
        sent.append(data)
        return _Response()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-1")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "chat-1")
    monkeypatch.setenv("DIRT_SERVICE_ALERT_STATE_PATH", str(state_path))
    monkeypatch.setenv("DIRT_SERVICE_ALERT_COOLDOWN_S", "900")
    monkeypatch.setattr(sys, "argv", ["telegram-alert", "dirt-camera.service"])
    monkeypatch.setattr(script.time, "time", fake_time)
    monkeypatch.setattr(script.subprocess, "check_output", lambda *_a, **_k: "tail")
    monkeypatch.setattr(script.urllib.request, "urlopen", fake_urlopen)

    assert script.main() == 0
    assert script.main() == 0

    assert len(sent) == 1
    assert json.loads(state_path.read_text()) == {
        "dirt-camera.service": {
            "last_sent_at": 1000.0,
            "suppressed_count": 1,
        }
    }


def test_service_alert_sends_after_cooldown_and_reports_suppressed_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    script = _load_script()
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "dirt-camera.service": {
                    "last_sent_at": 1000.0,
                    "suppressed_count": 3,
                }
            }
        )
    )
    sent: list[bytes] = []

    def fake_urlopen(_url: str, *, data: bytes, timeout: float) -> _Response:
        assert timeout == 10
        sent.append(data)
        return _Response()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-1")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "chat-1")
    monkeypatch.setenv("DIRT_SERVICE_ALERT_STATE_PATH", str(state_path))
    monkeypatch.setenv("DIRT_SERVICE_ALERT_COOLDOWN_S", "900")
    monkeypatch.setattr(sys, "argv", ["telegram-alert", "dirt-camera.service"])
    monkeypatch.setattr(script.time, "time", lambda: 2000.0)
    monkeypatch.setattr(script.subprocess, "check_output", lambda *_a, **_k: "tail")
    monkeypatch.setattr(script.urllib.request, "urlopen", fake_urlopen)

    assert script.main() == 0

    assert len(sent) == 1
    assert b"Suppressed+repeats+since+last+alert%3A+3" in sent[0]
    assert json.loads(state_path.read_text()) == {
        "dirt-camera.service": {
            "last_sent_at": 2000.0,
            "suppressed_count": 0,
        }
    }
