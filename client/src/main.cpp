#include <Arduino.h>

#include "command_processor.h"
#include "machine_config.h"
#include "mechanism.h"
#include "sensor.h"

Mechanism mechanism;
Sensor sensor;
CommandProcessor commands(Serial, mechanism, sensor);

void setup() {
  Serial.begin(SERIAL_BAUD);
  mechanism.begin();
  sensor.begin();
  commands.begin();
}

void loop() {
  // 三个 service 都必须被高频调用：串口接收、步进脉冲和后续传感器任务均按非阻塞方式推进。
  // 不要在 loop 中加入长时间 delay，否则会降低脉冲频率并延迟 STOP/POS? 等命令的处理。
  commands.service();
  mechanism.service();
  sensor.service();
 // long target[3] = {3000,3000,3000};
  //mechanism.moveToSteps(target);

  // 完成事件只消费一次，保证每次运动（包括平滑停止）只向上位机发送一条 DONE。
  if (mechanism.consumeMoveCompleted()) commands.reportMoveCompleted();
}
