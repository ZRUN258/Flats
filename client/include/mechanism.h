#pragma once

#include <AccelStepper.h>
#include <Arduino.h>

#include "machine_config.h"

class Mechanism {
 public:
  static constexpr uint8_t AXIS_COUNT = 3;
  enum Axis : uint8_t { AZIMUTH = 0, TILT = 1, RADIUS = 2 };
  enum Result : uint8_t { OK, LIMIT_ERROR };

  Mechanism();
  void begin();
  void service();

  Result moveToUnits(const float target[AXIS_COUNT]);
  Result moveToSteps(const long target[AXIS_COUNT]);
  Result jogSteps(Axis axis, long delta);
  void stopSmooth();
  void setZero();

  bool isIdle();
  bool consumeMoveCompleted();
  long currentSteps(Axis axis) const;
  long targetSteps(Axis axis) const;
  float currentUnits(Axis axis) const;
  static int8_t parseAxis(const char *name);

 private:
  AccelStepper azimuth_;
  AccelStepper tilt_;
  AccelStepper radius_;
  AccelStepper *steppers_[AXIS_COUNT];
  bool moveActive_ = false;
  bool wasIdle_ = true;

  bool positionAllowed(uint8_t axis, long step) const;
};
