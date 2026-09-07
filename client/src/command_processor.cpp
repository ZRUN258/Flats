#include "command_processor.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

namespace {
// strtod/strtol 会接受合法前缀（例如 "12abc" 中的 12），因此还需确认尾部只有空白。
// 严格解析可避免格式错误的坐标被当作有效运动指令执行。
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
  // 持续排空串口，使机构运动期间仍能响应 STOP、POS? 等命令。
  while (serial_.available()) {
    const char c = static_cast<char>(serial_.read());
    if (c == '\r') continue;
    if (c == '\n') {
      // 一旦溢出，整帧丢弃到换行处，避免把超长帧的尾部误识别成下一条命令。
      if (overflowed_) error(F("LINE_TOO_LONG"));
      else { rxBuffer_[rxLength_] = '\0'; execute(rxBuffer_); }
      rxLength_ = 0;
      overflowed_ = false;
    } else if (!overflowed_ && rxLength_ < RX_CAPACITY - 1) {
      rxBuffer_[rxLength_++] = c;
      if (rxLength_ == 2 && rxBuffer_[0] >= 'a' && rxBuffer_[0] <= 'f' &&
          rxBuffer_[1] >= '1' && rxBuffer_[1] <= '7') {
        // 旧协议固定为两个字节且没有换行符，只能在收满两字节时立即执行。
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
    // 三轴参数全部通过严格校验后才提交，防止半条指令导致部分轴先动作。
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
  // a/b、c/d、e/f 分别是三轴正/负方向；1..7 映射为离散点动步数。
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
  // 同时返回工程单位和整数步数：前者供界面显示，后者用于标定和无损状态核对。
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
