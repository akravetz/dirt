"""Entrypoint for the dirt hardware daemon (port 8000).

Owns the ESP32 sensor ingest endpoint and the four background loops
that exclusively touch hardware (serial reader, humidifier plug,
webcam capture, JPEG archive). Run as `dirt-hwd.service`.
"""

import uvicorn


def main() -> None:
    uvicorn.run(
        "dirt_hwd.app:app",
        host="0.0.0.0",
        port=8000,
    )


if __name__ == "__main__":
    main()
