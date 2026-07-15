#pragma once

#include <Arduino.h>

// Hardware placeholder values. Calibrate these after the mechanism is complete.
// The driver interface uses one pulse input for each direction (CW/CCW), matching
// the former firmware. Set positiveUsesCw=false if an axis moves oppositely.
struct AxisConfig {
  const char *name;
  uint8_t cwPin;
  uint8_t ccwPin;
  float unitsPerStep;       // degrees/step for angles, mm/step for radius
  bool positiveUsesCw;
  float maxSpeed;           // steps/second
  float acceleration;       // steps/second^2
};

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint16_t STEP_PULSE_US = 8;

// AZ: azimuth, TILT: 0 degrees at the pole, R: detector/sample distance.
constexpr AxisConfig AXIS_CONFIG[3] = {
    {"AZ",   10, 9, 0.010f, true, 1000.0f, 600.0f},
    {"TILT",  8, 7, 0.010f, true, 1000.0f, 600.0f},
    {"R",     6, 5, 0.001f, true, 1000.0f, 600.0f},
};

// Software limits are deliberately conservative placeholders. Set to false
// while commissioning if the real zero and travel have not been established.
constexpr bool LIMITS_ENABLED = false;
constexpr float MIN_POSITION[3] = {-180.0f, 0.0f, 0.0f};
constexpr float MAX_POSITION[3] = { 180.0f, 90.0f, 100.0f};

// Optional detector input. It is off by default because the current host uses
// a second serial port for laser/detector data. Enabling it adds MEASURE support.
constexpr bool ONBOARD_SENSOR_ENABLED = false;
constexpr uint8_t SENSOR_ANALOG_PIN = A0;
constexpr uint8_t SENSOR_SAMPLES = 16;
