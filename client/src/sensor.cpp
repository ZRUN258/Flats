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
  // Mega 2560 的 ADC 为 10 位；16 次最大和为 16368，uint32_t 可安全容纳。
  // 当前返回的是平均 ADC 码值，真实物理量换算应在传感器标定完成后加入。
  uint32_t sum = 0;
  for (uint8_t i = 0; i < SENSOR_SAMPLES; ++i) sum += analogRead(SENSOR_ANALOG_PIN);
  return {true, static_cast<float>(sum) / SENSOR_SAMPLES};
}
