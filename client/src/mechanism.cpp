#include "mechanism.h"

#include <math.h>
#include <string.h>

namespace {
// AccelStepper 的正/负回调先设置 DIR，再在 STEP 上产生一个有效脉冲。
void pulse(uint8_t pin) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(STEP_PULSE_US);
  digitalWrite(pin, LOW);
}

void step(uint8_t axis, bool positive) {
  const AxisConfig &config = AXIS_CONFIG[axis];
  const bool directionHigh = positive ? config.positiveDirectionHigh : !config.positiveDirectionHigh;
  digitalWrite(config.directionPin, directionHigh ? HIGH : LOW);
  delayMicroseconds(DIRECTION_SETUP_US);
  pulse(config.stepPin);
}

void positive0() { step(0, true); }
void negative0() { step(0, false); }
void positive1() { step(1, true); }
void negative1() { step(1, false); }
void positive2() { step(2, true); }
void negative2() { step(2, false); }
}  // namespace

Mechanism::Mechanism()
    : azimuth_(positive0, negative0),
      tilt_(positive1, negative1),
      radius_(positive2, negative2),
      steppers_{&azimuth_, &tilt_, &radius_} {}

void Mechanism::begin() {
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) {
    pinMode(AXIS_CONFIG[i].stepPin, OUTPUT);
    pinMode(AXIS_CONFIG[i].directionPin, OUTPUT);
    digitalWrite(AXIS_CONFIG[i].stepPin, LOW);
    digitalWrite(AXIS_CONFIG[i].directionPin,
                 AXIS_CONFIG[i].positiveDirectionHigh ? HIGH : LOW);
    steppers_[i]->setMaxSpeed(AXIS_CONFIG[i].maxSpeed);
    steppers_[i]->setAcceleration(AXIS_CONFIG[i].acceleration);
  }
}

void Mechanism::service() {
  // run() 每次最多推进当前时刻应产生的步进，必须由主循环高频、持续调用。
  for (auto *stepper : steppers_) stepper->run();
}

Mechanism::Result Mechanism::moveToUnits(const float target[AXIS_COUNT]) {
  long steps[AXIS_COUNT];
  // 只在协议边界进行一次四舍五入；内部始终用整数步，避免连续移动产生浮点累计误差。
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) steps[i] = lround(target[i] / AXIS_CONFIG[i].unitsPerStep);
  return moveToSteps(steps);
}

Mechanism::Result Mechanism::moveToSteps(const long target[AXIS_COUNT]) {
  // 先校验全部目标，再一次性更新三轴，保证越界时任何轴都不会改变目标位置。
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) if (!positionAllowed(i, target[i])) return LIMIT_ERROR;
  for (uint8_t i = 0; i < AXIS_COUNT; ++i) steppers_[i]->moveTo(target[i]);
  moveActive_ = !isIdle();
  wasIdle_ = !moveActive_;
  return OK;
}

Mechanism::Result Mechanism::jogSteps(Axis axis, long delta) {
  long target[AXIS_COUNT];
  // 相对点动叠加在“既有目标”而非瞬时位置上；运动中连续 JOG 不会丢失尚未走完的行程。
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
  // 这是纯软件置零，不会寻找原点；调用方必须保证机构静止且已位于已知基准位置。
  for (auto *stepper : steppers_) stepper->setCurrentPosition(0);
  moveActive_ = false;
  wasIdle_ = true;
}

bool Mechanism::isIdle() {
  for (auto *stepper : steppers_) if (stepper->distanceToGo() != 0) return false;
  return true;
}

bool Mechanism::consumeMoveCompleted() {
  // 用“运动中 -> 空闲”的状态沿生成一次性完成事件，避免主循环重复发送 DONE。
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
