#include "sensor.h"

#include "machine_config.h"

void Sensor::begin() {
  if (ONBOARD_SENSOR_ENABLED) pinMode(SENSOR_ANALOG_PIN, INPUT);
}

void Sensor::service() {
  // Reserved for a future non-blocking sensor state machine or serial sensor.
}

bool Sensor::available() const { return ONBOARD_SENSOR_ENABLED; }

SensorReading Sensor::measure() {
  if (!available()) return {false, 0.0f};
  uint32_t sum = 0;
  for (uint8_t i = 0; i < SENSOR_SAMPLES; ++i) sum += analogRead(SENSOR_ANALOG_PIN);
  return {true, static_cast<float>(sum) / SENSOR_SAMPLES};
}
