#ifndef PLANER_H
#define PLANER_H


#include"STEPPER.h"
#include"WIREMSG.h"
#include <Arduino.h>
int FeedRate = 1000;


class PLANER
{
  public:
    const byte MaxAxis;//这个规划器最多能控制几个轴（比如 2 轴或 3 轴）。
    PLANERSTATE State = None;//状态机。用来标记当前系统是在“待机”、“走直线”还是“走圆弧”。
    ARCMSG ArcMsg;//专门用来存储当前圆弧运动的所有计算数据（圆心、半径、步数）。
    STEPPER *Steppers;//指针数组。它动态地存储了所有被控制的电机对象。
    

    PLANER(byte axis) : MaxAxis(axis)
    {
      Steppers = new STEPPER[axis];
    }
    // 初始化串口
    void Begin(long baud)
     {
        Serial.begin(baud);
     }

    void AddAxis(byte cw, byte ccw, byte stpesPerMM, String id, AXISTYPE type = LinerAxis)
    {
      if (_axisNum >= MaxAxis)
      {
        return;
      }
      STEPPER stepper(cw, ccw,stpesPerMM, id, type);//创建一个 STEPPER 对象，并存入 Steppers 数组中
      Steppers[_axisNum++] = stepper;
    }

    int GetIndexByID(String id)
    {
      int index = -1;

      for (byte i = 0; i < _axisNum; i++)
      {
        if (Steppers[i].ID == id)
        {
          index = i;
          break;
        }
      }
      return index;
    };

    void CalculateArc(double x, double y, double r, bool isClockWise = false, bool isLargeArc = false)
    {
        // 确保电机指针有效
        if (_axisNum < 2) return; 
        
        State = isClockWise ? G02 : G03;//如果是顺时针，状态设为 G02；否则设为 G03，取决于 isClockWise
        
        // 调用圆弧计算
        ArcMsg.CalculateMsgByRadius(r, POINT(x, y), isClockWise, isLargeArc, &Steppers[0], &Steppers[1]);
    }

    void Planer()
    {
      switch (State)
      {
        case None:

          break;

        case G00:
        case G01:
          RunLine();
          break;

        case G02:// 顺时针圆弧
        case G03:// 逆时针圆弧
          RunArc();
          break;

      }
    }

    void RunLine()
    {
      if (IsAllStepperRunToTarget())
      {
        State = None;
      }
    }

// 假设你有一个全局变量 FeedRate (单位: mm/min)，例如 int FeedRate = 1000;
// 假设 ArcMsg 结构体包含: StepperA, StepperB, Steps, AlreadRunSteps, IsClockWise, CenterPoint, R, AngleA, Angle
   
      void RunArc()
      {
          // --- 1. 初始化阶段 (只在第一步运行) ---
          if (ArcMsg.AlreadRunSteps == 0)
          {
              // 计算两个轴各自的总步数
              // 注意： StepperA 对应 X，StepperB 对应 Y
              long stepsA = abs(ArcMsg.StepperA->TargetStep - ArcMsg.StepperA->CurrentStep);
              long stepsB = abs(ArcMsg.StepperB->TargetStep - ArcMsg.StepperB->CurrentStep);

              // 确定主轴 (谁步数多谁是主轴)
              // 如果 A 是主轴，B 就是从轴；反之亦然
              if (stepsA >= stepsB) {
                  ArcMsg.IsAMaster = true;
                  ArcMsg.TotalSteps = stepsA;
              } else {
                  ArcMsg.IsAMaster = false;
                  ArcMsg.TotalSteps = stepsB;
              }
              if (ArcMsg.TotalSteps == 0) { State = None; return; }

            float arcLength = ArcMsg.R * abs(ArcMsg.Angle);// 计算圆弧总长度 (用于计算速度)
            float timeForArc = arcLength / (FeedRate / 60.0);// 计算主轴每一步的时间间隔 (微秒),时间(秒) = 距离(mm) / 速度(mm/s)
            ArcMsg.StepDelay = (unsigned long)((timeForArc * 1000000.0) / ArcMsg.TotalSteps);
            
            // 限制最小延时，防止太快
            if(ArcMsg.StepDelay < 200) ArcMsg.StepDelay = 200;

            ArcMsg.LastStepTime = micros();
            ArcMsg.Error = 0;
          }

          // --- 2. 运行阶段 ---
          // 检查是否到了发下一个脉冲的时间
          if (micros() - ArcMsg.LastStepTime >= ArcMsg.StepDelay)
          {
              // 时间到了，更新计时器
              ArcMsg.LastStepTime = micros();

              // 判断是否结束
              if (ArcMsg.AlreadRunSteps >= ArcMsg.TotalSteps)
              {
                  State = None; // 运动结束
                  Serial.println("STATUS:IDLE");
                  return;
              }

              // --- 核心 DDA 算法 ---
              // 这里的逻辑是：主轴每走一步，从轴根据累加器决定是否走
              
              // 获取当前两个轴的位置和目标
              long currentA = ArcMsg.StepperA->CurrentStep;
              long targetA  = ArcMsg.StepperA->TargetStep;
              long currentB = ArcMsg.StepperB->CurrentStep;
              long targetB  = ArcMsg.StepperB->TargetStep;

              bool dirA = (targetA > currentA);
              bool dirB = (targetB > currentB);

              if (ArcMsg.IsAMaster)
              {
                  // A 是主轴：A 必须走，B 看情况走
                  ArcMsg.StepperA->Step(dirA); // 主轴发脉冲
                  
                  // 累加器逻辑
                  // 注意：这里用浮点数是为了精度，也可以用整数 Bresenham 算法
                  ArcMsg.Error += (float)abs(targetB - ArcMsg.StepperB->StartStep) / abs(targetA - ArcMsg.StepperA->StartStep);
                  
                  if (ArcMsg.Error >= 1.0) {
                      ArcMsg.StepperB->Step(dirB); // 从轴发脉冲
                      ArcMsg.Error -= 1.0;
                  }
              }
              else
              {
                  // B 是主轴：B 必须走，A 看情况走
                  ArcMsg.StepperB->Step(dirB); // 主轴发脉冲
                  
                  ArcMsg.Error += (float)abs(targetA - ArcMsg.StepperA->StartStep) / abs(targetB - ArcMsg.StepperB->StartStep);
                  
                  if (ArcMsg.Error >= 1.0) {
                      ArcMsg.StepperA->Step(dirA); // 从轴发脉冲
                      ArcMsg.Error -= 1.0;
                  }
              }

              ArcMsg.AlreadRunSteps++;

              // 发送位置反馈 (用于上位机显示)
              
              float angleNow = ArcMsg.AngleA + ArcMsg.Angle * ((float)ArcMsg.AlreadRunSteps / ArcMsg.Steps);
              POINT NewPoint;
              NewPoint.X = ArcMsg.CenterPoint.X + ArcMsg.R * cos(angleNow);
              NewPoint.Y = ArcMsg.CenterPoint.Y + ArcMsg.R * sin(angleNow);
              Serial.print("POS,"); 
              Serial.print(NewPoint.X,3); 
              Serial.print(",");
              Serial.println(NewPoint.Y,3);
             
          }
      }
    bool IsAllStepperRunToTarget()
    {
      bool isRuntoTarget = true;
      for (int i = 0; i < _axisNum; i++)
      {
        isRuntoTarget &= Steppers[i].RuntoTarget();
      }
      return isRuntoTarget;
    }


  private:
    byte _axisNum = 0;


};
#endif
