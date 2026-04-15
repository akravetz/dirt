#!/usr/bin/env bash
# Build dirt-camera-daemon.
# No external deps beyond g++ and the vendored libdev SDK.
set -euo pipefail
cd "$(dirname "$0")"

SRCS=(
    src/logger.cpp
    src/sdk_wrapper.cpp
    src/commands.cpp
    src/server.cpp
    src/main.cpp
)

OUT=dirt-camera-daemon

g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
    -pthread \
    -I vendor/libdev/include \
    -L vendor/libdev/lib \
    -Wl,-rpath,'$ORIGIN/vendor/libdev/lib' \
    -o "$OUT" "${SRCS[@]}" \
    -ldev -lpthread

echo "built: $(pwd)/$OUT"
