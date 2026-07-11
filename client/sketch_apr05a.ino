#include"PLANER.h"

PLANER StepperPlaner(2);
// hello world
// 定义变量用于存储接收到的数据
String inputString = "";         // 用于存储串口接收的字符串
bool stringComplete = false;     // 标记字符串是否接收完毕

void setup()
{
  Serial.begin(9600);
  inputString.reserve(50); // 预分配内存，防止内存碎片


  StepperPlaner.AddAxis(10, 9, 100, "X", LinerAxis);
  StepperPlaner.AddAxis(8, 7, 100, "Y", LinerAxis);

  Serial.println("ARDUINO_READY"); // 发送就绪信号给Python

 
}


void loop()
{
  // 1. 持续运行规划器 (处理电机脉冲生成)
  StepperPlaner.Planer();

  // 2. 处理串口数据
  if (stringComplete)
  {
    parseCommand(inputString);
    // 清空字符串以便接收下一条
    inputString = "";
    stringComplete = false;
  }
}

/*
   串口事件中断函数
   当有数据从 Python 发来时会触发此函数
*/
void serialEvent()
{
  while (Serial.available())
  {
    char inChar = (char)Serial.read();
    // 如果是换行符，表示一条指令结束
    if (inChar == '\n')
    {
      stringComplete = true;
    }
    else
    {
      inputString += inChar; // 累加字符
    }
  }
}

/*
   解析 Python 发来的指令
   预期格式: "ARC,X,Y,R" 例如: "ARC,50,50,60"
*/
void parseCommand(String command)
{
  // 简单的协议解析
  if (command.startsWith("ARC"))
  {
    // 移除 "ARC," 前缀
    String dataPart = command.substring(4);

    // 查找逗号位置
    int firstComma = dataPart.indexOf(',');
    int secondComma = dataPart.indexOf(',', firstComma + 1);

    if (firstComma > 0 && secondComma > 0)
    {
      // 提取 X, Y, R
      double x = dataPart.substring(0, firstComma).toDouble();
      double y = dataPart.substring(firstComma + 1, secondComma).toDouble();
      double r = dataPart.substring(secondComma + 1).toDouble();

      Serial.print("收到圆弧指令: X=");
      Serial.print(x);
      Serial.print(" Y=");
      Serial.print(y);
      Serial.print(" R=");
      Serial.println(r);
      StepperPlaner.CalculateArc(x, y, r, false, false);
    }
    else
    {
      Serial.println("错误: 数据格式不正确");
    }
  }
  else
  {
    Serial.print("未知指令: ");
    Serial.println(command);
  }
}

