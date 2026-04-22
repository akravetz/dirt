// Shared ArduinoOTA bring-up for dirt ESP32-C3 nodes.
//
// begin() wires up progress/error logging and starts the listener.
// loop() must be called frequently from the main loop to service updates.

#pragma once

#include <Arduino.h>

namespace ota {

void begin(const char* hostname, const char* password);
void loop();

}  // namespace ota
