#include "command_processor.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

namespace {
bool parseFloatStrict(const char *text, float &value) {
  char *end = nullptr;
  value = strtod(text, &end);
  while (end && isspace(*end)) ++end;
  return end != text && end && *end == '\0' && isfinite(value);
}

bool parseLongStrict(const char *text, long &value) {
  char *end = nullptr;
  value = strtol(text, &end, 10);
  while (end && isspace(*end)) ++end;
  return end != text && end && *end == '\0';
}
}  // namespace

CommandProcessor::CommandProcessor(Stream &serial, Mechanism &mechanism, Sensor &sensor)
    : serial_(serial), mechanism_(mechanism), sensor_(sensor) {}

void CommandProcessor::begin() {
  serial_.println(F("READY,FLATS_SPHERICAL,2"));
  printPosition(F("POS,IDLE,"));
}

void CommandProcessor::service() {
  while (serial_.available()) {
    const char c = static_cast<char>(serial_.read());
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflowed_) error(F("LINE_TOO_LONG"));
      else { rxBuffer_[rxLength_] = '\0'; execute(rxBuffer_); }
      rxLength_ = 0;
      overflowed_ = false;
    } else if (!overflowed_ && rxLength_ < RX_CAPACITY - 1) {
      rxBuffer_[rxLength_++] = c;
      if (rxLength_ == 2 && rxBuffer_[0] >= 'a' && rxBuffer_[0] <= 'f' &&
          rxBuffer_[1] >= '1' && rxBuffer_[1] <= '7') {
        rxBuffer_[2] = '\0';
        execute(rxBuffer_);
        rxLength_ = 0;
      }
    } else {
      overflowed_ = true;
    }
  }
}

void CommandProcessor::reportMoveCompleted() { printPosition(F("DONE,")); }

void CommandProcessor::execute(char *line) {
  while (isspace(*line)) ++line;
  char *tail = line + strlen(line);
  while (tail > line && isspace(tail[-1])) *--tail = '\0';
  if (!*line) return;
  if (strlen(line) == 2 && line[0] >= 'a' && line[0] <= 'f') { legacyJog(line[0], line[1]); return; }

  char *save = nullptr;
  char *command = strtok_r(line, ",", &save);
  if (!strcasecmp(command, "PING")) { serial_.println(F("PONG")); return; }
  if (!strcasecmp(command, "POS?") || !strcasecmp(command, "STATUS?")) {
    printPosition(mechanism_.isIdle() ? F("POS,IDLE,") : F("POS,MOVING,")); return;
  }
  if (!strcasecmp(command, "STOP")) {
    mechanism_.stopSmooth();
    serial_.println(F("ACK,STOPPING"));
    return;
  }
  if (!strcasecmp(command, "ZERO") || !strcasecmp(command, "SET_ZERO")) {
    if (!mechanism_.isIdle()) { error(F("BUSY")); return; }
    mechanism_.setZero();
    serial_.println(F("ACK,ZERO"));
    return;
  }
  if (!strcasecmp(command, "MOVE") || !strcasecmp(command, "GOTO")) {
    float units[Mechanism::AXIS_COUNT];
    for (uint8_t i = 0; i < Mechanism::AXIS_COUNT; ++i) {
      char *token = strtok_r(nullptr, ",", &save);
      if (!token || !parseFloatStrict(token, units[i])) { error(F("MOVE_FORMAT")); return; }
    }
    if (strtok_r(nullptr, ",", &save)) { error(F("MOVE_FORMAT")); return; }
    if (mechanism_.moveToUnits(units) == Mechanism::LIMIT_ERROR) error(F("LIMIT"));
    else serial_.println(mechanism_.isIdle() ? F("ACK,AT_TARGET") : F("ACK,MOVE"));
    return;
  }
  if (!strcasecmp(command, "MOVE_STEPS")) {
    long targets[Mechanism::AXIS_COUNT];
    for (uint8_t i = 0; i < Mechanism::AXIS_COUNT; ++i) {
      char *token = strtok_r(nullptr, ",", &save);
      if (!token || !parseLongStrict(token, targets[i])) { error(F("STEPS_FORMAT")); return; }
    }
    if (strtok_r(nullptr, ",", &save)) { error(F("STEPS_FORMAT")); return; }
    applyTargets(targets);
    return;
  }
  if (!strcasecmp(command, "JOG")) {
    char *name = strtok_r(nullptr, ",", &save);
    char *amount = strtok_r(nullptr, ",", &save);
    long delta;
    const int8_t axis = name ? Mechanism::parseAxis(name) : -1;
    if (axis < 0 || !amount || !parseLongStrict(amount, delta) || strtok_r(nullptr, ",", &save)) {
      error(F("JOG_FORMAT")); return;
    }
    const auto result = mechanism_.jogSteps(static_cast<Mechanism::Axis>(axis), delta);
    if (result == Mechanism::LIMIT_ERROR) error(F("LIMIT"));
    else serial_.println(mechanism_.isIdle() ? F("ACK,AT_TARGET") : F("ACK,MOVE"));
    return;
  }
  if (!strcasecmp(command, "MEASURE")) {
    if (!sensor_.available()) { error(F("SENSOR_EXTERNAL")); return; }
    if (!mechanism_.isIdle()) { error(F("BUSY")); return; }
    const SensorReading reading = sensor_.measure();
    if (!reading.valid) { error(F("SENSOR_READ")); return; }
    serial_.print(F("DATA,")); serial_.println(reading.value, 3);
    return;
  }
  error(F("UNKNOWN_CMD"));
}

void CommandProcessor::legacyJog(char direction, char sizeCode) {
  static const long increments[7] = {1, 2, 5, 10, 20, 50, 100};
  if (direction < 'a' || direction > 'f' || sizeCode < '1' || sizeCode > '7') {
    error(F("LEGACY_CMD")); return;
  }
  const auto axis = static_cast<Mechanism::Axis>((direction - 'a') / 2);
  const long sign = ((direction - 'a') % 2 == 0) ? 1 : -1;
  const auto result = mechanism_.jogSteps(axis, sign * increments[sizeCode - '1']);
  if (result == Mechanism::LIMIT_ERROR) error(F("LIMIT"));
  else serial_.println(F("ACK,MOVE"));
}

void CommandProcessor::printPosition(const __FlashStringHelper *prefix) {
  serial_.print(prefix);
  for (uint8_t i = 0; i < Mechanism::AXIS_COUNT; ++i) {
    if (i) serial_.print(',');
    serial_.print(mechanism_.currentUnits(static_cast<Mechanism::Axis>(i)), i == 2 ? 3 : 4);
  }
  serial_.print(F(",STEPS,"));
  for (uint8_t i = 0; i < Mechanism::AXIS_COUNT; ++i) {
    if (i) serial_.print(',');
    serial_.print(mechanism_.currentSteps(static_cast<Mechanism::Axis>(i)));
  }
  serial_.println();
}

void CommandProcessor::error(const __FlashStringHelper *code) {
  serial_.print(F("ERR,")); serial_.println(code);
}

bool CommandProcessor::applyTargets(const long target[Mechanism::AXIS_COUNT]) {
  if (mechanism_.moveToSteps(target) == Mechanism::LIMIT_ERROR) { error(F("LIMIT")); return false; }
  serial_.println(mechanism_.isIdle() ? F("ACK,AT_TARGET") : F("ACK,MOVE"));
  return true;
}
