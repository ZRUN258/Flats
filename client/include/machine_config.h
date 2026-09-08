#pragma once

#include <Arduino.h>

// 以下硬件参数均为占位值，机构装配完成后必须逐轴标定。
// 驱动器使用 STEP/DIR 输入；原 cwPin 作为脉冲脚，原 ccwPin 作为方向脚。
// 若协议正方向与实机相反，只修改 positiveDirectionHigh，
// 不要交换上位机坐标含义。
struct AxisConfig {
  const char *name;
  uint8_t stepPin;
  uint8_t directionPin;
  float unitsPerStep;       // degrees/step for angles, mm/step for radius
  bool positiveDirectionHigh;
  float maxSpeed;           // steps/second
  float acceleration;       // steps/second^2
};

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint16_t STEP_PULSE_US = 8;
constexpr uint16_t DIRECTION_SETUP_US = 5;

// AZ：方位角；TILT：极点为 0°；R：探头/样品的径向距离。
// unitsPerStep 决定协议单位到整数步数的映射，更改细分或传动比后必须同步重标定。
constexpr AxisConfig AXIS_CONFIG[3] = {
    {"AZ",   10, 9, 0.05625f, false, 500.0f, 600.0f},
    {"TILT",  8, 7, 0.010f, false, 1000.0f, 600.0f},
    {"R",     6, 5, 0.001f, false, 1000.0f, 600.0f},
};

// 软件限位按工程单位检查“目标位置”，不能替代独立硬限位和急停。
// 当前范围也是占位值；真实零点和行程未确认前保持关闭，确认后再启用。
constexpr bool LIMITS_ENABLED = false;
constexpr float MIN_POSITION[3] = {-180.0f, 0.0f, 0.0f};
constexpr float MAX_POSITION[3] = { 180.0f, 90.0f, 100.0f};

// 可选板载检测输入。当前方案由上位机通过第二串口采集，因此默认关闭；
// 启用后 MEASURE 才会读取 A0，返回值目前仍是未标定的平均 ADC 码值。
constexpr bool ONBOARD_SENSOR_ENABLED = false;
constexpr uint8_t SENSOR_ANALOG_PIN = A0;
constexpr uint8_t SENSOR_SAMPLES = 16;
