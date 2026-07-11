import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtWidgets, uic
import serial
import time

class ArcApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui_15_3.ui", self)  # 加载 UI 文件

        # 获取控件
        self.pushbutton_start_arc = self.findChild(QtWidgets.QPushButton, 'pushbutton_start_arc')
        self.pushbutton_stop_arc = self.findChild(QtWidgets.QPushButton, 'pushbutton_stop_arc')
        self.lineedit_end_x = self.findChild(QtWidgets.QLineEdit, 'lineedit_end_x')
        self.lineEdit_end_y = self.findChild(QtWidgets.QLineEdit, 'lineEdit_end_y')
        self.lineEdit_curvature_radius = self.findChild(QtWidgets.QLineEdit, 'lineEdit_curvature_radius')
        self.laserDisp_groupBox = self.findChild(QtWidgets.QGroupBox, 'laserDisp_groupBox')

        # 绑定按钮事件
        self.pushbutton_start_arc.clicked.connect(self.start_arc)
        self.pushbutton_stop_arc.clicked.connect(self.stop_arc)

        # 初始化绘图区域
        self.figure, self.ax = plt.subplots(figsize=(6, 6))
        self.canvas = FigureCanvas(self.figure)

        # 为 laserDisp_groupBox 设置一个布局（VBoxLayout）
        layout = QtWidgets.QVBoxLayout(self.laserDisp_groupBox)
        layout.addWidget(self.canvas)

        # 设置坐标轴
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_xlabel('X轴 (mm)')
        self.ax.set_ylabel('Y轴 (mm)')
        self.ax.grid(True)

        # 翻转Y轴使原点在左下角
        self.ax.invert_yaxis()
        try:
            self.ser = serial.Serial('COM5', 115200, timeout=1)
            time.sleep(2) # 等待串口连接稳定
            print("串口已打开")
        except Exception as e:
            print(f"串口打开失败: {e}")
            self.ser = None

    def send_command(self, cmd):
        """辅助函数：发送指令并添加换行符"""
        if self.ser and self.ser.is_open:
            # 加上 \n 是为了让 Arduino 识别指令结束
            full_cmd = f"{cmd}\n"
            self.ser.write(full_cmd.encode('utf-8'))
            # 简单的延时，防止串口缓冲区溢出，实际项目中可用信号槽优化
            time.sleep(0.005) 
            print(f"发送: {cmd}")

    def start_arc(self):
        try:
            # 获取用户输入的终点坐标和半径
            target_x = float(self.lineedit_end_x.text())
            target_y = float(self.lineEdit_end_y.text())
            radius = float(self.lineEdit_curvature_radius.text())

            # 调用绘制圆弧的核心方法
            self.draw_arc_logic(target_x, target_y, radius)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "输入错误", "请输入有效的数字")

    def stop_arc(self):
        # 清除当前的绘图
        self.ax.clear()
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_xlabel('X轴 (mm)')
        self.ax.set_ylabel('Y轴 (mm)')
        self.ax.grid(True)
        self.canvas.draw()

    def draw_arc_logic(self, target_x, target_y, radius):
        """
        核心算法：圆弧插补逻辑
        在图上绘制圆弧。
        """
        # 1. 初始化参数
        curr_x = 0.0
        curr_y = 0.0
        
        # 如果终点和起点重合，直接返回
        if abs(curr_x - target_x) < 0.01 and abs(curr_y - target_y) < 0.01:
            print("起点与终点重合，无需绘制")
            return

        # 2. 寻找圆心
        mid_x = (curr_x + target_x) / 2
        mid_y = (curr_y + target_y) / 2
        
        # 计算起点到终点的距离的一半
        half_dist = math.sqrt((target_x - curr_x)**2 + (target_y - curr_y)**2) / 2
        
        # 保护：如果半径小于弦长的一半，无法构成圆弧
        if radius < half_dist:
            print(f"半径 {radius} 太小，无法连接起点和终点")
            return
            
        # 计算圆心到弦中点的距离 (勾股定理)
        h = math.sqrt(radius**2 - half_dist**2)
        
        # 计算圆心坐标 
        dx = target_x - curr_x
        dy = target_y - curr_y
        length = math.sqrt(dx**2 + dy**2)
        ux = -dy / length
        uy = dx / length
        
        center_x = mid_x + ux * h
        center_y = mid_y + uy * h
        
        # 计算起点的角度和终点的角度
        start_angle = math.atan2(curr_y - center_y, curr_x - center_x)
        end_angle = math.atan2(target_y - center_y, target_x - center_x)
        
        # 确保角度是递增的 (逆时针画弧)
        if end_angle <= start_angle:
            end_angle += 2 * math.pi
            
        total_angle = end_angle - start_angle

        # 3. 插补循环
        steps = int(total_angle * radius * 10)  # 根据弧长决定步数，每0.1mm一步
        steps = max(steps, 10)  # 至少10步
        
        print(f"开始画圆弧: 半径{radius}, 步数{steps}")

        # 存储圆弧坐标
        x_values = [curr_x]  # 确保圆弧从 (0, 0) 开始
        y_values = [curr_y]

        for i in range(1, steps + 1):
            # 计算当前插补点的角度和坐标
            current_angle = start_angle + (total_angle * i / steps)
            next_x = center_x + radius * math.cos(current_angle)
            next_y = center_y + radius * math.sin(current_angle)


            delta_x = next_x - curr_x
            delta_y = next_y - curr_y
            # 发送指令给 Arduino
            # 过滤掉极小的数值，防止电机抖动
            if abs(delta_x) > 0.05: 
                self.send_command(f"X{delta_x:.2f}")
            if abs(delta_y) > 0.05:
                self.send_command(f"Y{delta_y:.2f}")

            # 更新当前坐标（用于下一次计算）
            curr_x = next_x
            curr_y = next_y
            # 保存当前点的坐标
            x_values.append(next_x)
            y_values.append(next_y)

        # 绘制圆弧路径
        self.ax.clear()  # 清除之前的图形
        self.ax.plot(x_values, y_values, label="圆弧轨迹", color="blue")
        self.ax.scatter(0, 0, color='red', label="起点(0,0)")  # 起点
        self.ax.scatter(x_values[-1], y_values[-1], color='green', label=f"终点({x_values[-1]}, {y_values[-1]})")  # 圆弧终点

        # 设置坐标轴
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_xlabel('X轴 (mm)')
        self.ax.set_ylabel('Y轴 (mm)')
        self.ax.grid(True)
        self.ax.legend()

        # 刷新图形
        self.canvas.draw()

# 启动应用
if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = ArcApp()
    window.show()
    app.exec_()