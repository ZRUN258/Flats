# 半球面检测运动控制器

Arduino Mega 2560 控制三个步进轴：方位角 `AZ`、倾斜角 `TILT` 和半径/探头距离 `R`。
电机采用原工程的双脉冲接口（每轴 CW、CCW 各一个脉冲引脚）。所有运动均以整数步执行，
不存在累计的浮点位置误差。运动规划使用成熟的 `AccelStepper` 库，支持可配置的最大速度和加减速，
避免电机突然启停。

## 模块结构

- `mechanism.*`：机构、三轴、球坐标到步数的映射和运动状态；
- `command_processor.*`：串口收包、协议解析和上位机响应；
- `sensor.*`：传感器抽象及采集入口，目前默认使用外部串口方案；
- `machine_config.h`：硬件引脚、方向、标定值、速度和限位；
- `main.cpp`：只组装模块并调度非阻塞任务。

## 校准入口

编辑 `include/machine_config.h`：

- `cwPin` / `ccwPin`：电机驱动器引脚；
- `unitsPerStep`：角度轴单位为 度/步，半径轴单位为 mm/步；
- `positiveUsesCw`：实际方向相反时改为 `false`；
- `maxSpeed`：最大速度，单位 步/秒；
- `acceleration`：加速度，单位 步/秒²；
- `LIMITS_ENABLED` 和 `MIN_POSITION` / `MAX_POSITION`：机械限位完成后启用。

当前占位值：两个角度轴 `0.01 度/步`，半径轴 `0.001 mm/步`。

## 串口协议

115200 baud，ASCII，一条命令以换行结束：

```text
MOVE,方位角度,倾斜角度,半径mm
MOVE_STEPS,方位步数,倾斜步数,半径步数
JOG,AZ|TILT|R,相对步数
POS?
STOP
ZERO
PING
MEASURE
```

示例：`MOVE,30.5,20,8.25\n`。控制器立即回复 `ACK,MOVE`，到位后回复：

```text
DONE,30.5000,20.0000,8.250,STEPS,3050,2000,8250
```

`MOVE_STEPS` 和 `JOG` 可直接验证单步精度。尚无原点开关时，`ZERO` 仅把当前位置设为软件零点，
必须在电机静止时使用。`STOP` 会按配置的加速度平滑减速，不能替代硬件急停。

现有上位机发送的两字节 `a1..f7` 命令仍受支持：`a/b`、`c/d`、`e/f` 分别对应三轴正反向，
`1..7` 对应 1、2、5、10、20、50、100 步。

## 检测数据通道

现有上位机创建了独立的 `motor_port` 和 `laser_port`，采集/激光数据不经过运动控制板，默认保持该方案。
因此 `ONBOARD_SENSOR_ENABLED=false`，发送 `MEASURE` 会返回 `ERR,SENSOR_EXTERNAL`。若将来传感器接到
Mega 的模拟口，可启用该开关；固件会在静止时对 A0 采样并返回 `DATA,value`。
