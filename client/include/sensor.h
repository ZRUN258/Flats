#pragma once

#include <Arduino.h>

struct SensorReading {
  bool valid;
  float value;
};

class Sensor {
 public:
  void begin();
  void service();
  bool available() const;
  SensorReading measure();
};
