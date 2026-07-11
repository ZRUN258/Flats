#ifndef _STEPPER_h
#define _STEPPER_h

enum AXISTYPE
{
  RotaAxis = 0,
  LinerAxis,
};

class STEPPER
{
  public:
    byte CwPin, CcwPin;
    long CurrentStepTime = 0, TargetStepTime = 500, LastStepSt = 0;
    long CurrentStep = 0, TargetStep = 0, StartStep = 0;
    long Acceleration = 6000;//加速度(步/秒~2）
    long SpeedUpStep, SpeedDownStep;//加速,减速时的步数
    bool IsDebug = false;
    byte StepsPerMM =  100;
    AXISTYPE AxisType;
    String ID = "";

    STEPPER()
    {

    }

    STEPPER(byte cw, byte ccw, byte stpesPerMM, String id, AXISTYPE type = LinerAxis)
    {
      CwPin = cw;
      CcwPin = ccw;
      
      
      StepsPerMM = stpesPerMM;
      ID = id;
      AxisType = type;
      calCulateSpeedChangeMinimunDis();

      pinMode(CwPin, OUTPUT);
      pinMode(CcwPin, OUTPUT);
   

      digitalWrite(CwPin, 0);
      digitalWrite(CcwPin, 0);
     
      
    }
    
    void SetTarGet(double coordinate)
    {
      //目标步数 = 坐标 × 每毫米步数
      TargetStep = (long) ceil(coordinate *  StepsPerMM);
    }

     //规划路径
    void SetAcceleration(long acceleration)
    {
      Acceleration = acceleration;
      calCulateSpeedChangeMinimunDis();
    }

    bool IsRunToTarget()
    {
      return TargetStep == CurrentStep;
    }

    bool CanRun()
    {
      return micros() - LastStepSt >= CurrentStepTime;
    }

    bool RuntoTarget()
    {
      if (IsRunToTarget() == false)
      {
        if (CanRun())
        {
          runStep(CurrentStep < TargetStep);
        }
      }
      return IsRunToTarget();
    }

    bool RunTo(long target)
    {
      if (TargetStep != target)
      {
        TargetStep = target;
        CurrentStepTime = 0;
        StartStep = CurrentStep;
        calCulateSpeedChangeMinimunDis();
        if (IsDebug)
        { /*
            Serial.print ("V: ");
            Serial.println (1000000.0 / TargetStepTime);

            Serial.print ("_speedChangeMinimumDis: ");
            Serial.println (_speedChangeMinimumDis);
            Serial.print ("StartStep: ");
            Serial.println (StartStep);*/
        }
        long souldMoveSteps = TargetStep - CurrentStep;

        if ( _speedChangeMinimumDis * 2 > abs(souldMoveSteps))
        {
          SpeedUpStep =  souldMoveSteps / 2 + CurrentStep;
          SpeedDownStep = SpeedUpStep;
        }

        else
        {
          if (CurrentStep < TargetStep)//正向
          {
            SpeedUpStep =  _speedChangeMinimumDis + CurrentStep;
            SpeedDownStep = TargetStep - _speedChangeMinimumDis;
          }
          else//反向
          {
            SpeedUpStep =  CurrentStep - _speedChangeMinimumDis;
            SpeedDownStep = TargetStep + _speedChangeMinimumDis;
          }
        }
        if (IsDebug)
        {
          /*
                    Serial.print ("SpeedUpStep: ");
                    Serial.println (SpeedUpStep);
                    Serial.print ("SpeedDownStep: ");
                    Serial.println (SpeedDownStep);
          */
        }
      }

      RuntoTarget();

      return IsRunToTarget();
    }

    void RunCycle(bool dir,  unsigned long stepTime)
    {
      TargetStepTime = stepTime;
      CurrentStepTime = 0;
      if (CanRun())
      {
        runStep( dir);
      }
    }

  private:
    long _speedChangeMinimumDis = 0;

    void calCulateSpeedChangeMinimunDis()
    {
      double v = 1000000.0 / TargetStepTime;//步/秒
      _speedChangeMinimumDis =  pow(v, 2) / 2 / Acceleration;
    }

    void runStep(bool dir)
    {
      LastStepSt = micros();
      if(dir) {
        // 顺时针
        digitalWrite(CwPin, HIGH);
        delayMicroseconds(10);
        digitalWrite(CwPin, LOW);
        CurrentStep ++;
    } else {
        // 逆时针
        digitalWrite(CcwPin, HIGH);
        delayMicroseconds(10);
        digitalWrite(CcwPin, LOW);
        CurrentStep --;
    }


      if (Acceleration == 0)
      {
        CurrentStepTime = TargetStepTime ;
        return;
      }
      double v = 0.0;// =  CurrentStepTime > 0 ? 1000000.0 / CurrentStepTime  : 0;//步/秒
      if (dir)
      {
        if (CurrentStep < SpeedUpStep || CurrentStep > SpeedDownStep)
        {
          if (CurrentStep < SpeedUpStep)
          {
            v = sqrt(double( Acceleration * 2.0 * (CurrentStep - StartStep)));//步/秒
          }
          else
          {
            v = 1000000.0 / TargetStepTime;//步/秒
            v = sqrt(double((-Acceleration) * 2.0 * (CurrentStep - SpeedDownStep )  +  pow(v, 2)));//步/秒
          }
          CurrentStepTime = 1000000.0 / v;
          CurrentStepTime = CurrentStepTime <= TargetStepTime ? TargetStepTime : CurrentStepTime;
        }

        else
        {
          CurrentStepTime = TargetStepTime ;
        }
      }

      else
      {
        if (CurrentStep > SpeedUpStep || CurrentStep < SpeedDownStep)
        {
          if (CurrentStep > SpeedUpStep)
          {
            v = sqrt(Acceleration * 2 * (StartStep - CurrentStep));//步/秒
          }
          else
          {
            v = 1000000.0 / TargetStepTime;//步/秒
            v = sqrt((-Acceleration) * 2 * abs(CurrentStep - SpeedDownStep)  +  pow(v, 2));//步/秒
          }
          CurrentStepTime = 1000000.0 / v;
          CurrentStepTime = CurrentStepTime <= TargetStepTime ? TargetStepTime : CurrentStepTime;
        }

        else
        {
          CurrentStepTime = TargetStepTime ;
        }
      }
      if (IsDebug)
      {
        // Serial.print (CurrentStep);
        //Serial.print (",");
        Serial.print ( v == 0 ? 1000000.0 / CurrentStepTime : v);
        Serial.print (",");
        Serial.println (CurrentStepTime);
      }
    }
};


#endif
