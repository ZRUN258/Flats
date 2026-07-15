#include "mechanism.h"

#include <math.h>
#include <string.h>

namespace {
void pulse(uint8_t pin) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(STEP_PULSE_US);
  digitalWrite(pin, LOW);
}

void positive0() { pulse(AXIS_CONFIG[0].positiveUsesCw ? AXIS_CONFIG[0].cwPin : AXIS_CONFIG[0].ccwPin); }
void negative0() { pulse(AXIS_CONFIG[0].positiveUsesCw ? AXIS_CONFIG[0].ccwPin : AXIS_CONFIG[0].cwPin); }
void positive1() { pulse(AXIS_CONFIG[1].positiveUsesCw ? AXIS_CONFIG[1].cwPin : AXIS_CONFIG[1].ccwPin); }
void negative1() { pulse(AXIS_CONFIG[1].positiveUsesCw ? AXIS_CONFIG[1].ccwPin : AXIS_CONFIG[1].cwPin); }
void positive2() { pulse(AXIS_CONFIG[2].positiveUsesCw ? AXIS_CONFIG[2].cwPin : AXIS_CONFIG[2].ccwPin); }
void negative2() { pulse(AXIS_CONFIG[2].positiveUsesCw ? AXIS_CONFIG[2].ccwPin : AXIS_CONFIG[2].cwPin); }
}  // namespace

Mechanism::Mechanism()
    : azimuth_(positive0, negative0),
      tilt_(positive1, negative1),
      radius_(positive2, negative2),
      steppers_{&azimuth_, &tilt_, &radius_} {}

void Mechanism::begin() {
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) {
    pinMode(AXIS_CONFIG[i].cwPin, OUTPUT);
    pinMode(AXIS_CONFIG[i].ccwPin, OUTPUT);
    digitalWrite(AXIS_CONFIG[i].cwPin, LOW);
    digitalWrite(AXIS_CONFIG[i].ccwPin, LOW);
    steppers_[i]->setMaxSpeed(AXIS_CONFIG[i].maxSpeed);
    steppers_[i]->setAcceleration(AXIS_CONFIG[i].acceleration);
  }
}

void Mechanism::service() {
  for (auto *stepper : steppers_) stepper->run();
}

Mechanism::Result Mechanism::moveToUnits(const float target[AXIS_COUNT]) {
  long steps[AXIS_COUNT];
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) steps[i] = lround(target[i] / AXIS_CONFIG[i].unitsPerStep);
  return moveToSteps(steps);
}

Mechanism::Result Mechanism::moveToSteps(const long target[AXIS_COUNT]) {
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) if (!positionAllowed(i, target[i])) return LIMIT_ERROR;
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) steppers_[i]->moveTo(target[i]);
  moveActive_ = !isIdle();
  wasIdle_ = !moveActive_;
  return OK;
}

Mechanism::Result Mechanism::jogSteps(Axis axis, long delta) {
  long target[AXIS_COUNT];
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) target[i] = steppers_[i]->targetPosition();
  target[axis] += delta;
  return moveToSteps(target);
}

void Mechanism::stopSmooth() {
  // AccelStepper::stop() computes a deceleration target; service() must continue.
  for (auto *stepper : steppers_) stepper->stop();
  moveActive_ = !isIdle();
  wasIdle_ = !moveActive_;
}

void Mechanism::setZero() {
  for (auto *stepper : steppers_) stepper->setCurrentPosition(0);
  moveActive_ = false;
  wasIdle_ = true;
}

bool Mechanism::isIdle() {
  for (auto *stepper : steppers_) if (stepper->distanceToGo() != 0) return false;
  return true;
}

bool Mechanism::consumeMoveCompleted() {
  const bool idle = isIdle();
  const bool completed = moveActive_ && !wasIdle_ && idle;
  wasIdle_ = idle;
  if (completed) moveActive_ = false;
  return completed;
}

long Mechanism::currentSteps(Axis axis) const { return steppers_[axis]->currentPosition(); }
long Mechanism::targetSteps(Axis axis) const { return steppers_[axis]->targetPosition(); }
float Mechanism::currentUnits(Axis axis) const { return currentSteps(axis) * AXIS_CONFIG[axis].unitsPerStep; }

int8_t Mechanism::parseAxis(const char *name) {
  if (!strcasecmp(name, "AZ") || !strcasecmp(name, "A") || !strcmp(name, "0")) return AZIMUTH;
  if (!strcasecmp(name, "TILT") || !strcasecmp(name, "T") || !strcmp(name, "1")) return TILT;
  if (!strcasecmp(name, "R") || !strcasecmp(name, "RADIUS") || !strcmp(name, "2")) return RADIUS;
  return -1;
}

bool Mechanism::positionAllowed(uint8_t axis, long step) const {
  if (!LIMITS_ENABLED) return true;
  const float value = step * AXIS_CONFIG[axis].unitsPerStep;
  return value >= MIN_POSITION[axis] && value <= MAX_POSITION[axis];
}
