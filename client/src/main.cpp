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
  commands.service();
  mechanism.service();
  sensor.service();
  if (mechanism.consumeMoveCompleted()) commands.reportMoveCompleted();
}
