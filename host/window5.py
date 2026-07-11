import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtWidgets, uic

import configparser
import os
import re
import sys
import time

# import serial.tools.list_ports
from PyQt5.QtWidgets import QGridLayout
from matplotlib.lines import Line2D

import string_process
from my_figure_canvas import MyFigureCanvas
from my_serial_port import *
from ui_15_3 import Ui_MainWindow
from board_ctrl import *

class MyQThread(QtCore.QThread):
    """
    重新构造一个QThread类，使用信号改变主线程里的对象
    run方法重写
    """
    #  定义一个基础信号量并且传递str类型数据
    signals = QtCore.pyqtSignal(str)

    def __init__(self):
        """
        父类初始化
        """
        super().__init__()
        self.is_working = True

    def __del__(self):
        """
        线程状态改变与线程终止
        """
        self.is_working = False
        self.wait()

    def run(self):
        """
        等待重定义
        """
        while self.is_working:
            start = time.time()
            for i in range(10):
                self.msleep(100)
            end = time.time()
            print(end - start)


class PortUI:
    """
    因为有两个串口，所以把他们相似的UI设计和部分逻辑提取出来，就是左上方倒着的L的一个区域
    """

    class QThreadUpdatePortState(MyQThread):
        """
        起个线程，控制实时显示串口状态
        """

        def __init__(self):
            """
            # 无
            """
            super().__init__()

        def run(self):
            """
            run函数，0.01s更新
            """
            while self.is_working:
                self.msleep(10)
                self.signals.emit("")  # 发送信号让其更新

    class QThreadRxData(MyQThread):
        """
        线程：定时接受数据并且显示
        """

        # 串口接受到的数据是byte类型的，这里对应的是关联函数的两个输入参数
        signals = QtCore.pyqtSignal(str, bytes)

        def __init__(self, my_serial_port: MySerialPort):
            """
            # description 一定确保ser的准确性
            """
            super().__init__()
            self.my_serial_port = my_serial_port

        def run(self):
            """
            run函数，0.001s更新
            """
            while self.is_working:
                self.msleep(10)

                if self.my_serial_port.isOpen():
                    try:
                        # * 设置无限期等待, 等不到阻塞, 挂起该线程
                        self.my_serial_port.timeout = None
                        # * 尝试读取一个字节
                        temp_data = (self.my_serial_port.read(1))
                        # * 查看是否还有字节未读取, 获取缓存中的字节大小
                        byte_count = self.my_serial_port.inWaiting()
                        # * 如果有
                        if byte_count == 0 and type(temp_data) == bytes:
                            self.my_serial_port.rx_byte_count += 1
                        elif byte_count > 0:
                            # * 直接读取
                            temp_data += (self.my_serial_port.read(byte_count))
                            self.my_serial_port.rx_byte_count += (1 + byte_count)
                        # * 发送信号, 调用关联函数, 显示到textbrowser上
                        self.signals.emit('receive : ', temp_data)
                    except Exception as ep:
                        print(str(ep))
                        traceback.print_exc()

    def __init__(self, arduino_label: str, my_serial_port: MySerialPort, my_parent_window,
                 combobox_name: QtWidgets.QComboBox,
                 combobox_baudrate: QtWidgets.QComboBox, combobox_bytesize: QtWidgets.QComboBox,
                 combobox_stopbits: QtWidgets.QComboBox, combobox_parity: QtWidgets.QComboBox,
                 pushbutton_open_port: QtWidgets.QPushButton, pushbutton_refresh_port: QtWidgets.QPushButton,
                 label_name: QtWidgets.QLabel, label_baudrate: QtWidgets.QLabel, label_rxcnt: QtWidgets.QLabel,
                 label_txcnt: QtWidgets.QLabel, checkbox_hex_disp: QtWidgets.QCheckBox,
                 checkbox_pause_disp: QtWidgets.QCheckBox, checkbox_time_stamp: QtWidgets.QCheckBox,
                 pushbutton_clear_disp: QtWidgets.QPushButton, textbrowser_data_disp: QtWidgets.QPushButton,
                 checkbox_disp_send: QtWidgets.QCheckBox, textedit_tx_data: QtWidgets.QTextEdit,
                 checkbox_hex_send: QtWidgets.QCheckBox, checkbox_send_newline: QtWidgets.QCheckBox,
                 pushbutton_clear_send_edit: QtWidgets.QPushButton, pushbutton_send_data: QtWidgets.QPushButton):

        self.my_serial_port = my_serial_port  # 串口模块
        self.my_parent_window = my_parent_window  # 父窗口，尽量减少使用，以免造成混乱
        self.arduino_label = arduino_label

        # 下面的这些名字在界面中都能找到对应的，都是对应UI设计中的空间
        self.combobox_name = combobox_name
        self.combobox_baudrate = combobox_baudrate
        self.combobox_bytesize = combobox_bytesize
        self.combobox_stopbits = combobox_stopbits
        self.combobox_parity = combobox_parity
        self.pushbutton_open_port = pushbutton_open_port
        self.pushbutton_refresh_port = pushbutton_refresh_port
        self.label_name = label_name
        self.label_baudrate = label_baudrate
        self.label_rxcnt = label_rxcnt
        self.label_txcnt = label_txcnt
        self.checkbox_hex_disp = checkbox_hex_disp
        self.checkbox_pause_disp = checkbox_pause_disp
        self.checkbox_time_stamp = checkbox_time_stamp
        self.pushbutton_clear_disp = pushbutton_clear_disp
        self.textbrowser_data_disp = textbrowser_data_disp  # 显示收发信息的文本框
        self.checkbox_disp_send = checkbox_disp_send  # 是否显示发送内容
        self.textedit_tx_data = textedit_tx_data
        self.checkbox_hex_send = checkbox_hex_send
        self.checkbox_send_newline = checkbox_send_newline
        self.pushbutton_clear_send_edit = pushbutton_clear_send_edit
        self.pushbutton_send_data = pushbutton_send_data

        # 绑定槽函数：串口开关
        self.pushbutton_open_port.clicked.connect(self.slot_pushbutton_open_port)
        # 绑定槽函数：刷新串口
        self.pushbutton_refresh_port.clicked.connect(self.refresh_port)
        # 绑定槽函数：清空文本框
        self.pushbutton_clear_disp.clicked.connect(self.clear_disp)
        # 绑定槽函数，发送数据
        self.pushbutton_send_data.clicked.connect(lambda: self.send_data(None))
        # 绑定槽函数，清空发送框
        self.pushbutton_clear_send_edit.clicked.connect(self.clear_send_edit)

        # 创建、关联、启动线程
        self.qthread_update_port_state = self.QThreadUpdatePortState()
        self.qthread_update_port_state.signals.connect(self.update_port_state)
        self.qthread_update_port_state.start()

        self.qthread_rx_data = self.QThreadRxData(self.my_serial_port)
        self.qthread_rx_data.signals.connect(self.disp_data)
        self.qthread_rx_data.start()

    def ui_init(self):
        """
        初始化ui界面上的显示
        :return:
        """

        # 先刷新一下串口
        self.refresh_port()
        # 波特率
        self.combobox_baudrate.setCurrentIndex(8)
        # 数据位
        self.combobox_bytesize.setCurrentIndex(3)
        # 校验位
        self.combobox_parity.setCurrentIndex(2)
        # 停止位
        self.combobox_stopbits.setCurrentIndex(1)

    def refresh_port(self):
        """
        description 刷新串口, 并更新在combobox_name里
        param {*}
        return {若存在则返回temp_port_name_list}
        """
        try:
            # 清空目前的combobox_port_name
            self.combobox_name.clear()
            # 获取端口名称列表
            temp_port_name_list = get_port_dev()
            # 直接显示到combobox_port_name
            # 若存在可用端口
            if not temp_port_name_list == []:
                # 逐个加入
                for each_temp_port_name in temp_port_name_list:
                    self.combobox_name.addItem(each_temp_port_name)
                # 顺便返回一下端口
                return temp_port_name_list
        # 报个错
        except Exception as ep:
            self.my_parent_window.show_err(str(ep))
            traceback.print_exc()

    def control_port(self, expect_state):
        """
        description 管理串口的开关，并且更新对应的ui界面
        param {*}
        return {*}
        """
        back_msg = True  # 保存报错信息
        # 若要打开端口
        if expect_state == 'open':
            self.my_serial_port.port = ''  # 先清空掉吧
            # 如果端口处于关闭状并且存在串口的话
            if not self.my_serial_port.isOpen() and not self.combobox_name.count() == 0:
                # 数据位：
                bytesize_dict = {'5': serial.FIVEBITS, '6': serial.SIXBITS, '7': serial.SEVENBITS,
                                 '8': serial.EIGHTBITS}
                # 校验位：PARITY_NONE, PARITY_EVEN, PARITY_ODD, PARITY_MARK, PARITY_SPACE = 'N', 'E', 'O', 'M', 'S'
                parity_dict = {'Even': serial.PARITY_EVEN, 'Mark': serial.PARITY_MARK, 'None': serial.PARITY_NONE,
                               'Odd': serial.PARITY_ODD, 'Space': serial.PARITY_SPACE}
                # 停止位：STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO = (1, 1.5, 2)
                stopbits_dict = {'1': serial.STOPBITS_ONE, '1.5': serial.STOPBITS_ONE_POINT_FIVE,
                                 '2': serial.STOPBITS_TWO}

                # 设置串口参数
                self.my_serial_port.set_port(self.combobox_name.currentText(),
                                             int(self.combobox_baudrate.currentText()),
                                             bytesize_dict[self.combobox_bytesize.currentText()],
                                             parity_dict[self.combobox_parity.currentText()],
                                             stopbits_dict[self.combobox_stopbits.currentText()])

                back_msg = self.my_serial_port.open_port()
                if back_msg is True:
                    self.pushbutton_open_port.setText("关闭串口")
            # 如果端口已经开启或者不存在串口的话，报错
            else:
                back_msg = 'Opening conditions are not met'
        # 如果要求关闭端口
        else:
            if self.my_serial_port.isOpen():
                # 尝试
                try:
                    # 直接关闭串口就可以了
                    self.my_serial_port.close()
                    # 关闭成功更新按键内容
                    self.my_serial_port.port = ''
                    self.pushbutton_open_port.setText("打开串口")
                    back_msg = True
                # 报错
                except Exception as ep:
                    traceback.print_exc()
                    back_msg = str(ep)  # 错误的话保存报错信息
            else:
                back_msg = 'Serial port is not opened'

        # 如果出现错误情况，直接报错
        if back_msg is not True:
            self.my_parent_window.show_err(str(back_msg))

    def slot_pushbutton_open_port(self):
        """
        # description 槽函数, 连接pushbutton_open_port
        # 按照设置, 打开或者关闭串口
        """
        if self.pushbutton_open_port.text() == "打开串口":
            self.control_port('open')
        elif self.pushbutton_open_port.text() == "关闭串口":
            self.control_port('close')

    def update_port_state(self):
        green_color = '60b53b'
        red_color = 'ff0000'
        if self.my_serial_port.isOpen():
            color = green_color
        else:
            color = red_color

        html_txt = "<html><head/><body><p><span style=\" font-weight:600; color:#" + color + ";\">" \
                   + self.arduino_label + ":" + self.my_serial_port.port + "</span></p></body></html>"
        self.label_name.setText(QtCore.QCoreApplication.translate("MainWindow", html_txt))
        self.label_baudrate.setText('波特率:' + str(self.my_serial_port.baudrate))
        self.label_rxcnt.setText('R:' + str(self.my_serial_port.rx_byte_count))
        self.label_txcnt.setText('T:' + str(self.my_serial_port.tx_byte_count))

    def disp_data(self, head, temp_bytes=None):
        """
        description 在textbrowser按照显示设置显示temp_bytes
        param {bytes类型的待显示数据}
        param {head, 自定义加在disp_data前面的, 如"收 : ","发 : ", 只有选择加时间戳该head才生效}
        return {返回显示的字符串}
        """
        if temp_bytes is None:
            return
            # 使用utf-8标准进行解码
        try:
            # 如果没有选择暂停显示
            if not self.checkbox_pause_disp.isChecked():
                # 如果选择了16进制(HEX)显示
                if self.checkbox_hex_disp.isChecked():
                    # temp_bytes转16进制字符串
                    temp_str = string_process.bytes_to_hexstr(temp_bytes)
                    # 将16进制字符按照两个一组分开,变列表
                    temp_str_list = re.findall(".{2}", temp_str)
                    # 中间使用空格连接
                    temp_str = " ".join(temp_str_list)
                    temp_str = temp_str + ' '
                else:
                    # temp_str = temp_bytes.encode('utf-8')
                    temp_str = temp_bytes.decode('utf-8')
                # 如果要求加上时间戳，并且分包显示
                if self.checkbox_time_stamp.isChecked():
                    # 加上时间戳
                    temp_str = string_process.add_time_stamp(temp_str)
                    temp_str = head + temp_str

                # textbrowser_data_disp 显示数据
                self.textbrowser_data_disp.insertPlainText(temp_str)
                # 将textbrowser_data_disp 拉到最后一行
                self.textbrowser_data_disp.moveCursor(
                    self.textbrowser_data_disp.textCursor().End)

        except Exception as ep:
            # 详细打印错误给自己看
            traceback.print_exc()
            # 将错误显示到警告弹出窗口上
            self.my_parent_window.show_err(str(ep))

    def clear_disp(self):
        """
        description 清空rx计数和textbrowser_data_disp
        param {*}
        return {*}
        """
        # 清空textbrowser_data_disp
        self.textbrowser_data_disp.clear()
        # 清空rx计数
        self.my_serial_port.rx_byte_count = 0

    def send_data(self, data=None):
        """
        description 读取文本框里信息并发送数据
        param {*}
        return {*}
        """
        # 如果串口没打开, 报个错
        if not self.my_serial_port.isOpen():
            # 报错, 返回错误
            self.my_parent_window.show_err("串口未打开")
            print("串口未打开")
            return False

        # 尝试发送数据
        try:
            # 从input文本框中获取发送数据
            if data is None:
                temp_str = self.textedit_tx_data.toPlainText()
            else:
                temp_str = data

            if type(temp_str) == bytes:
                # 如果是bytes直接不管了直接发送
                temp_bytes = data
            elif type(temp_str) == str:
                # 转为utf-8编码
                temp_bytes = temp_str.encode('utf-8')
                # 如果输入的是16进制, 则重新处理
                if self.checkbox_hex_send.isChecked():
                    # 清理干净无关的符号
                    temp_str = string_process.purify_hexstr(temp_str)
                    # 判断是否为一串16进制字符串
                    if not string_process.is_hexstr(temp_str):
                        # 报错
                        self.my_parent_window.show_err(
                            "输入十六进制以','或'，'或' '分隔,\r\n若无分割请确保两个数字表示一个16进制")
                        return
                    # 16进制字符串转bytes
                    temp_bytes = string_process.hexstr_to_bytes(temp_str)
                # 如果要发送新行
                if self.checkbox_send_newline.isChecked():
                    # 加上\r\n
                    temp_bytes = temp_bytes + b'\r\n'

            # 发送数据
            self.my_serial_port.write(temp_bytes)

            # 保存长度
            self.my_serial_port.tx_byte_count += len(temp_bytes)

            if self.checkbox_disp_send.isChecked():
                self.disp_data("send : ", temp_bytes)

        # 出错了，报出警告
        except Exception as ep:
            self.my_parent_window.show_err(str(ep))
            traceback.print_exc()

        # 返回发出去的数据
        return temp_bytes

    def clear_send_edit(self):
        """
        description 清空tx计数和textedit_tx_data
        param {*}
        return {*}
        """
        # 清空textedit_tx_data
        self.textedit_tx_data.clear()
        # 清空tx计数
        self.my_serial_port.tx_byte_count = 0

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
        
        # 动态创建两个 QLabel 控件，用于显示电机坐标和状态
        self.label_motor_position = QtWidgets.QLabel(self)
        self.label_motor_position.setText("电机坐标: X=0.00 cm, Y=0.00 cm")
        self.label_motor_position.move(20, 400)  # 设置位置
        self.label_motor_position.show()

        self.label_motor_status = QtWidgets.QLabel(self)
        self.label_motor_status.setText("电机状态: 停止")
        self.label_motor_status.move(20, 430)  # 设置位置
        self.label_motor_status.show()

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

        # 初始化电机模拟状态
        self.curr_x = 0.0  # in cm
        self.curr_y = 0.0  # in cm

    def start_arc(self):
        try:
            # 获取用户输入的终点坐标和半径
            target_x_mm = float(self.lineedit_end_x.text())  # in mm
            target_y_mm = float(self.lineedit_end_y.text())  # in mm
            radius_mm = float(self.lineedit_curvature_radius.text())  # in mm

            # 转换为厘米：将输入的毫米数乘以10
            target_x = target_x_mm * 10  # Convert mm to cm
            target_y = target_y_mm * 10  # Convert mm to cm
            radius = radius_mm * 10  # Convert mm to cm

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
        模拟电机沿着圆弧路径逐步移动，XY电机同步控制。
        """
        # 1. 初始化参数
        curr_x = self.curr_x  # in cm
        curr_y = self.curr_y  # in cm
        
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

            # 保存当前点的坐标
            x_values.append(next_x)
            y_values.append(next_y)

            # 计算步长的差异，控制电机同步移动
            self.move_motor(next_x, next_y)
            # 更新界面上的电机坐标和状态
            self.update_motor_status(next_x, next_y, "电机正在移动")

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
        # 更新状态为电机停止
        self.update_motor_status(x_values[-1], y_values[-1], "电机停止")

    def update_motor_status(self, x, y, status):
        """
        更新电机坐标和状态
        """
        self.label_motor_position.setText(f"电机坐标: X={x:.2f} cm, Y={y:.2f} cm")
        self.label_motor_status.setText(f"电机状态: {status}")

    def move_motor(self, next_x, next_y):
        """
        同步控制X和Y方向的电机，使两个电机同时到达终点。
        """
        # 计算电机移动的距离
        diff_x = next_x - self.curr_x
        diff_y = next_y - self.curr_y

        # 计算电机的步长
        step_x = diff_x  # X方向的步长
        step_y = diff_y  # Y方向的步长

        # 计算每个电机的比例
        max_step = max(abs(step_x), abs(step_y))  # 获取最大步长
        time_x = max_step / abs(step_x) if step_x != 0 else 0  # X电机的时间比例
        time_y = max_step / abs(step_y) if step_y != 0 else 0  # Y电机的时间比例

        # 确保两个电机的时间相同，取最大时间
        total_time = max(time_x, time_y)

        # 计算电机需要同步的速度
        speed_x = step_x / total_time  # X方向的速度
        speed_y = step_y / total_time  # Y方向的速度

        # 模拟电机同步移动
        print(f"电机从 ({self.curr_x:.4f}, {self.curr_y:.4f}) 移动到 ({next_x:.4f}, {next_y:.4f})")
        
        # 更新电机当前位置
        self.curr_x = next_x
        self.curr_y = next_y

       
    
if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = ArcApp()
    window.show()
    app.exec_()