#pragma once

#include <Arduino.h>

#include "mechanism.h"
#include "sensor.h"

class CommandProcessor {
 public:
  CommandProcessor(Stream &serial, Mechanism &mechanism, Sensor &sensor);
  void begin();
  void service();
  void reportMoveCompleted();

 private:
  static constexpr size_t RX_CAPACITY = 96;
  Stream &serial_;
  Mechanism &mechanism_;
  Sensor &sensor_;
  char rxBuffer_[RX_CAPACITY] = {};
  size_t rxLength_ = 0;
  bool overflowed_ = false;

  void execute(char *line);
  void legacyJog(char direction, char sizeCode);
  void printPosition(const __FlashStringHelper *prefix);
  void error(const __FlashStringHelper *code);
  bool applyTargets(const long target[Mechanism::AXIS_COUNT]);
};
