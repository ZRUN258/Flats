#define ARC_SECTION_MM 0.5


class POINT
{
  public:
    double X;
    double Y;

    POINT() : X(0), Y(0) {}
    POINT(double x, double y) : X(x), Y(y) {}
};

enum PLANERSTATE { None = 0, G00, G01, G02, G03 };
class LINEMSG
{
  public:
    POINT StartPoint, EndPoint;
    double Length;
    unsigned int Steps = 0, AlreadRunSteps = 1;

    void CalculateMsg(POINT startPoint, POINT endPoint)
    {
      //TODO:并联机械手直线分段插补数据计算
    }
};

class ARCMSG : public LINEMSG
{
  public:
    POINT  CenterPoint;

    double Angle, AngleA, AngleB;
    double R;
    bool IsClockWise = false;
   

    STEPPER *StepperA;
    STEPPER *StepperB;
    long Steps;           // 总步数（主轴的步数）
    long AlreadRunSteps;  // 当前已走步数
    bool IsAMaster;       // A轴是否是主轴
    long TotalSteps;      // 总步数
    unsigned int StepDelay; // 每一步的时间间隔（微秒）
    unsigned long LastStepTime; // 上一次发脉冲的时间
    float Error;          // DDA累加器
    long StartStepA;      // 记录A轴起始步数
    long StartStepB;      // 记录B轴起始步数
   

     void CalculateMsgByRadius(double radius, POINT endPoint, bool isClockWise, bool isLargeArc, STEPPER *a, STEPPER *b)
    {
        POINT startPoint(0, 0); // 强制起点为原点
        POINT centerPoint;
        
        double x = endPoint.X;
        double y = endPoint.Y;
        double r = radius;
        
        a->CurrentStep = 0;
        a->StartStep = 0;
        b->CurrentStep = 0;
        b->StartStep = 0;

        // 计算目标步数 (终点坐标 * 步数/mm)
        // 注意：这里假设你的 STEPPER 类里有 StepsPerMM 变量
        a->TargetStep = (long)(x * a->StepsPerMM);
        b->TargetStep = (long)(y * b->StepsPerMM);

        // --- 关键修复 2: 调试输出，看看步数算出来是多少 ---
        Serial.print("Debug: Steps A = "); Serial.println(a->TargetStep);
        Serial.print("Debug: Steps B = "); Serial.println(b->TargetStep);

        // 如果终点就是原点，没必要动
        if (a->TargetStep == 0 && b->TargetStep == 0) {
            Serial.println("Info: Target is Origin, no move.");
            State = None;
            

        // 如果终点距离起点的距离 > 直径，则无法连接
        double dist = sqrt(x*x + y*y);
        if (dist > 2 * r) {
            // 无法到达，错误处理
            Serial.println("Error: Radius too small to reach endpoint");
            return;
        }

        // 计算圆心坐标：圆心在两点连线的中垂线上
        double d_sq = x*x + y*y;
        double h = sqrt(r*r - d_sq/4.0); // 圆心到弦的中点的垂直距离

        // 中点坐标
        double mx = x / 2.0;
        double my = y / 2.0;

        // 圆心有两个解 (cx1, cy1) 和 (cx2, cy2)
        double cx1 = mx + (h * y) / sqrt(d_sq);
        double cy1 = my - (h * x) / sqrt(d_sq);
        
        double cx2 = mx - (h * y) / sqrt(d_sq);
        double cy2 = my + (h * x) / sqrt(d_sq);

        //  选择正确的圆心
        // 我们需要判断哪个圆心对应顺时针，哪个对应逆时针，以及是否是大圆弧
        // 简单策略：先默认选一个，再通过角度判断是否符合 isLargeArc
        
        // 这里我们先尝试使用 cx1, cy1
        CenterPoint.X = cx1;
        CenterPoint.Y = cy1;

        // 临时计算一下角度跨度，看看是不是我们要的弧
        double tempAngleA = atan2(startPoint.Y - CenterPoint.Y, startPoint.X - CenterPoint.X);
        double tempAngleB = atan2(endPoint.Y - CenterPoint.Y, endPoint.X - CenterPoint.X);
        double tempSweep = 0;

        if (isClockWise) {
            // 顺时针：起点角度 -> 终点角度 (逆着算)
            tempSweep = tempAngleA - tempAngleB;
            if (tempSweep <= 0) tempSweep += 2 * PI;0000000000000000000000;
        } else {
            // 逆时针
            tempSweep = tempAngleB - tempAngleA;
            if (tempSweep <= 0) tempSweep += 2 * PI;
        }

        // 如果计算出的弧度不匹配用户要求的 (比如用户要大弧，算出的是小弧)，则切换到另一个圆心
        bool isCurrentArcLarge = (tempSweep > PI);
        if (isCurrentArcLarge != isLargeArc) {
            CenterPoint.X = cx2;
            CenterPoint.Y = cy2;
        }

        this->CalculateMsg(startPoint, endPoint, CenterPoint, isClockWise, a, b);
    }
    void CalculateMsg(POINT startPoint, POINT endPoint, POINT centerPoint, bool isClockWise, STEPPER *a, STEPPER *b)
    {
      StartPoint = startPoint;
      EndPoint = endPoint;
      CenterPoint = centerPoint;
      IsClockWise = isClockWise;
      StepperA = a;
      StepperB = b;

      double aX = StartPoint.X - CenterPoint.X;
      double aY = StartPoint.Y - CenterPoint.Y;
      double bX = EndPoint.X - CenterPoint.X;
      double bY = EndPoint.Y - CenterPoint.Y;

      if (IsClockWise)
      {
        AngleA = atan2(bY, bX);
        AngleB = atan2(aY, aX);
      }
      else
      {
        AngleA = atan2(aY, aX);
        AngleB = atan2(bY, bX);
      }

      if (AngleB <= AngleA)
      {
        AngleB += 2 * PI;
      }

      Angle = AngleB - AngleA;
      R = sqrt(aX * aX + aY * aY);
      Length = R * Angle;

      Steps = (unsigned int) ceil(Length / ARC_SECTION_MM);
      AlreadRunSteps = 1;
    }
};
/*
      Serial.println("AngleA: " + String(AngleA, 5));
      Serial.println("AngleB: " + String(AngleB, 5));
      Serial.println("Angle: " + String(Angle, 5));
      Serial.println("R: " + String(R, 5));
      Serial.println("Steps: " + String(Steps));
      Serial.println("Length: " + String(Length, 5));

      Serial.println( );
      */
    





