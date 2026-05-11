from pathlib import Path

from dirt_gateway import main
from dirt_shared.config import CaptureConfig


class FakeSettings:
    def __init__(self, *, socket_path: Path, snapshot_dir: Path) -> None:
        self._socket_path = socket_path
        self._snapshot_dir = snapshot_dir

    def capture(self) -> CaptureConfig:
        return CaptureConfig(
            snapshot_dir=self._snapshot_dir,
            capture_interval=300,
            camera_socket_path=self._socket_path,
        )


def test_gateway_ptz_service_uses_configured_camera_socket(monkeypatch, tmp_path):
    socket_path = tmp_path / "runtime" / "dirt-camera.sock"
    calls: dict[str, object] = {}

    def fake_rpc_for_socket(path: Path):
        calls["socket_path"] = path

        async def fake_rpc(line: str) -> dict[str, str]:
            return {"_status": "error", "line": line}

        return fake_rpc

    class FakePTZService:
        def __init__(self, *, rpc):
            calls["rpc"] = rpc

    monkeypatch.setattr(main, "daemon_rpc_for_socket", fake_rpc_for_socket)
    monkeypatch.setattr(main, "PTZService", FakePTZService)

    ptz = main._gateway_ptz_service(
        FakeSettings(
            socket_path=socket_path,
            snapshot_dir=tmp_path / "snapshots",
        )
    )

    assert isinstance(ptz, FakePTZService)
    assert calls["socket_path"] == socket_path
    assert "rpc" in calls
