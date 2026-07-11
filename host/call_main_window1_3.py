import configparser
import os
import re
import sys
import time
import serial
import serial.tools.list_ports

import numpy as np

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QGridLayout

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal

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



# 【核心】串口读取线程
class SerialThread(QtCore.QThread):
    # 定义信号，用于把数据传回主界面
    data_received = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.is_running = True


    def run(self):
        while self.is_running:
            if self.serial_port.isOpen():
               
                try:
                    raw_data = self.serial_port.readline()
                    if raw_data:
                         #会跳过无法解析的字节，防止程序崩溃
                          line = self.serial_port.readline().decode('utf-8').strip()
                    if line:
                        if line.startswith("POS"):
                            # 发送坐标信号给主界面
                            self.data_received.emit(line)
                        elif line.startswith("STATUS"):
                            # 发送状态信号
                            self.status_update.emit(line)
                except Exception as e:
                    print(f"串口读取异常: {e}")
            else:
                self.msleep(100)



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


class CtrlAreaUI:
    class QThreadAutoPrint(MyQThread):
        """
        线程：定时接受数据并且显示
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
                self.msleep(20)
                self.signals.emit("")  # 发送信号让其更新

    def __init__(self, motor_serial_port: MySerialPort, laser_serial_port: MySerialPort, my_parent_window,
                 groupbox_ctrl_area: QtWidgets.QGroupBox):
        self.motor_serial_port = motor_serial_port  # 串口模块
        self.laser_serial_port = laser_serial_port  # 串口模块
        self.my_parent_window = my_parent_window  # 父类窗口
        self.groupbox_ctrl_area = groupbox_ctrl_area  # 控制区UI
        BoardParam['moving_countdown'].timeout.connect(self.motor_move_end)  # 移动结束执行该函数
        BoardParam['laser_dly_countdown'].timeout.connect(self.stop_laser)  # 移动结束执行该函数

        # ---------------------------------------不要管-----------------------------------------------------
        self.groupbox_param_cfg = self.groupbox_ctrl_area.findChild(QtWidgets.QGroupBox, 'groupbox_param_cfg')
        self.groupbox_manual_ctrl = self.groupbox_ctrl_area.findChild(QtWidgets.QGroupBox, 'groupbox_manual_ctrl')
        self.group_auto_ctrl = self.groupbox_ctrl_area.findChild(QtWidgets.QGroupBox, 'group_auto_ctrl')

        self.label_laser_freq = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_laser_freq')
        self.lineedit_laser_freq = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_laser_freq')
        self.label_laser_duty = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_laser_duty')
        self.lineedit_laser_duty = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_laser_duty')
        self.label_laser_num = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_laser_num')
        self.lineedit_laser_num = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_laser_num')

        self.label_estimated_movement_time = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel,
                                                                               'label_estimated_movement_time')
        self.lineedit_estimated_movement_time = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit,
                                                                                  'lineedit_estimated_movement_time')
        
        self.label_end_x = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_end_x')
        self.lineedit_end_x= self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_end_x')
        self.label_end_y = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_end_y')
        self.lineedit_end_y = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_end_y')
        self.label_curvature_radius = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_curvature_radius')
        self.lineedit_curvature_radius = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_curvature_radius')

        self.pushbutton_open_laser = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_open_laser')
        self.pushbutton_close_laser = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_close_laser')
        self.pushbutton_start_arc = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_start_arc')
        self.pushbutton_stop_arc = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_stop_arc')

        self.pushbutton_move_xp = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_move_xp')
        self.pushbutton_move_xn = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_move_xn')
        self.pushbutton_move_yp = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_move_yp')
        self.pushbutton_move_yn = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_move_yn')
        self.pushbutton_move_zp = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_move_zp')
        self.pushbutton_move_zn = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_move_zn')

        self.combobox_x_move_range = self.groupbox_ctrl_area.findChild(QtWidgets.QComboBox, 'combobox_x_move_range')
        self.combobox_y_move_range = self.groupbox_ctrl_area.findChild(QtWidgets.QComboBox, 'combobox_y_move_range')
        self.combobox_z_move_range = self.groupbox_ctrl_area.findChild(QtWidgets.QComboBox, 'combobox_z_move_range')

        self.checkbox_use_cfg = self.groupbox_ctrl_area.findChild(QtWidgets.QCheckBox, 'checkbox_use_cfg')
        self.label_file_path = self.groupbox_ctrl_area.findChild(QtWidgets.QLabel, 'label_file_path')
        self.lineedit_file_path = self.groupbox_ctrl_area.findChild(QtWidgets.QLineEdit, 'lineedit_file_path')
        self.pushbutton_open_file = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_open_file')
        self.pushbutton_read_file = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_read_file')
        self.pushbutton_start_print = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_start_print')
        self.pushbutton_stop_print = self.groupbox_ctrl_area.findChild(QtWidgets.QPushButton, 'pushbutton_stop_print')
        # ---------------------------------------不要管-----------------------------------------------------
        self.pushbutton_move_xp.clicked.connect(
            lambda: self.start_motor_move(MOVE_CMD[0][self.combobox_x_move_range.currentIndex()],
                                          int(self.lineedit_estimated_movement_time.text())))
        self.pushbutton_move_xn.clicked.connect(
            lambda: self.start_motor_move(MOVE_CMD[1][self.combobox_x_move_range.currentIndex()],
                                          int(self.lineedit_estimated_movement_time.text())))
        self.pushbutton_move_yp.clicked.connect(
            lambda: self.start_motor_move(MOVE_CMD[2][self.combobox_y_move_range.currentIndex()],
                                          int(self.lineedit_estimated_movement_time.text())))
        self.pushbutton_move_yn.clicked.connect(
            lambda: self.start_motor_move(MOVE_CMD[3][self.combobox_y_move_range.currentIndex()],
                                          int(self.lineedit_estimated_movement_time.text())))
        self.pushbutton_move_zp.clicked.connect(
            lambda: self.start_motor_move(MOVE_CMD[4][self.combobox_z_move_range.currentIndex()],
                                          int(self.lineedit_estimated_movement_time.text())))
        self.pushbutton_move_zn.clicked.connect(
            lambda: self.start_motor_move(MOVE_CMD[5][self.combobox_z_move_range.currentIndex()],
                                          int(self.lineedit_estimated_movement_time.text())))

        self.pushbutton_open_laser.clicked.connect(
            lambda: self.set_laser_freq(self.lineedit_laser_freq.text(),  # 强度
                                        self.lineedit_laser_duty.text(),  # 占空比
                                        int(self.lineedit_laser_num.text())))  # 具体数值
        self.pushbutton_close_laser.clicked.connect(self.stop_laser)

        self.pushbutton_start_arc.clicked.connect(self.start_drawing_arc)
        self.pushbutton_stop_arc.clicked.connect(self.stop_drawing_arc)
      


        self.pushbutton_open_file.clicked.connect(self.open_file)
        self.pushbutton_read_file.clicked.connect(self.read_track_file)
        self.pushbutton_start_print.clicked.connect(self.start_print)
        self.pushbutton_stop_print.clicked.connect(self.stop_print)

        self.track_from_array_x = []  # 从csv_array中规划来的路径，x坐标
        self.track_from_array_y = []  # 从csv_array中规划来的路径，y坐标
        self.csv_array = []  # 存储csv中读到的数据
        self.now_step = -1  # 用于统计自动打印情况下，当前的打印进度

        self.qthread_auto_print = self.QThreadAutoPrint()  # 开一个线程，实现自动打印
        self.qthread_auto_print.signals.connect(self.auto_print)  # 连接自动打印函数
        self.qthread_auto_print.start()

    def open_file(self):
        """
        准确来说是获取文件夹的路径，并保存到文本框里
        这个函数没问题
        :return:
        """
        try:
            # 建立一个文件对话框
            file_name = QtWidgets.QFileDialog.getOpenFileName(self.my_parent_window, '打开文件', './')
            # 挑选选择的第一个文件
            if file_name[0]:
                with open(file_name[0], 'r', encoding='gb18030', errors='ignore') as f:
                    # f.name即为文件的绝对路径
                    self.lineedit_file_path.setText(str(f.name))
        except Exception as ep:
            self.my_parent_window.show_err(str(ep))
            traceback.print_exc()

    def read_track_file(self):
        """
        获取轨迹文件，并且解析得到轨迹，并保存起来
        这个函数没问题
        :return:
        """
        try:
            # 直接获取轨迹文件
            self.csv_array = read_track_xlsx(self.lineedit_file_path.text())
            self.track_from_array_x, self.track_from_array_y = get_track_from_array(self.csv_array)
        except Exception as ep:
            self.my_parent_window.show_err(str(ep))
            traceback.print_exc()

 # 在 CtrlAreaUI 类中添加发送逻辑
    def start_drawing_arc(self,estimated_movement_time):
        try:
            # 获取输入框数据
            x = self.lineedit_end_x.text()
            y = self.lineedit_end_y.text()
            r = self.lineedit_curvature_radius.text()

            if x and y and r:
                # 组合成指令: ARC,x,y,r\n
                cmd = f"ARC,{x},{y},{r}\n"
                # 通过电机串口发送给 Arduino
                self.motor_serial_port.write(cmd.encode('utf-8'))
                print(f"指令已下发: {cmd.strip()}")
                
                # 初始化轨迹记录
                BoardParam['track_x'] = []
                BoardParam['track_y'] = []
                BoardParam['is_motor_moving'] = True
                BoardParam['estimated_movement_time'] = estimated_movement_time  # 记录这次移动预估所需要花费的时间

                 # 开始移动，计时器计数
                BoardParam['moving_countdown'].start(BoardParam['estimated_movement_time'])

                # 如果是自动打印，令打印状态为正在移动中
                if BoardParam['is_printing']:
                    BoardParam['print_steps'] = 'in move'
                else:
                    # 这里锁定界面，移动过程中禁止进行有关操作
                    for i in self.groupbox_ctrl_area.findChildren(QtWidgets.QPushButton):
                        i.setEnabled(False)
            else:
                self.my_parent_window.show_err("请输入完整的 X, Y, R 参数")
        except Exception as e:
            self.my_parent_window.show_err(f"发送圆弧指令失败: {e}")         
    def stop_drawing_arc(self):
       
        BoardParam['is_motor_moving'] = False  # 标志位显示移动结束
        BoardParam['moving_countdown'].stop()  # 关闭定时器

        # 如果是自动打印，现在状态变为移动结束
        if BoardParam['is_printing']:
            BoardParam['print_steps'] = 'move end'
        else:
            for i in self.groupbox_ctrl_area.findChildren(QtWidgets.QPushButton):  # 打开相关界面操作的权限
                i.setEnabled(True)  

    def start_motor_move(self, move_cmd, estimated_movement_time):
        """
        按照指令，控制电机移动，该函数会自动计算实时轨迹和当前坐标
        这里需要输入移动时间, 默认的就是
        :param estimated_movement_time: 默认的是int(self.lineedit_estimated_movement_time.text())
        :param move_cmd: 行动指令
        :return:
        """
        if move_cmd is None:
            return

        BoardParam['estimated_movement_time'] = estimated_movement_time  # 记录这次移动预估所需要花费的时间
        BoardParam['is_motor_moving'] = True  # 标志位改成True，证明电机正在移动
        # 发送移动指令 并且 显示
        self.motor_serial_port.send_bytes(move_cmd)
        if self.my_parent_window.motor_port_ui.checkbox_disp_send.isChecked():
            self.my_parent_window.motor_port_ui.disp_data("send : ", move_cmd)

        # 该部分直接计算坐标增量和记录，轨迹，轨迹单位是cm，坐标单位是um
        tmp_idx = np.argwhere(MOVE_CMD == move_cmd)[0]  # 找到命令对应的下角标，并显示坐标叠加，其实这里应该是理论上到达的坐标
        if tmp_idx[0] % 2 == 0:  # 偶数说明前进
            BoardParam['motor_coord'][tmp_idx[0] // 2] += STEP_SIZE[tmp_idx[1]]
        elif tmp_idx[0] % 2 == 1:  # 奇数说明后退
            BoardParam['motor_coord'][tmp_idx[0] // 2] -= STEP_SIZE[tmp_idx[1]]
        BoardParam['track_x'].append(BoardParam['motor_coord'][0] * 1e-6)  # 按照目前坐标更新轨迹
        BoardParam['track_y'].append(BoardParam['motor_coord'][1] * 1e-6)
        BoardParam['track_z'].append(BoardParam['motor_coord'][2] * 1e-6)

        # 开始移动，计时器计数
        BoardParam['moving_countdown'].start(BoardParam['estimated_movement_time'])

        # 如果是自动打印，令打印状态为正在移动中
        if BoardParam['is_printing']:
            BoardParam['print_steps'] = 'in move'
        else:
            # 这里锁定界面，移动过程中禁止进行有关操作
            for i in self.groupbox_ctrl_area.findChildren(QtWidgets.QPushButton):
                i.setEnabled(False)

    def motor_move_end(self):
        """
        电机结束移动，该函数主要与计时器关联
        :return:
        """
        BoardParam['is_motor_moving'] = False  # 标志位显示移动结束
        BoardParam['moving_countdown'].stop()  # 关闭定时器

        # 如果是自动打印，现在状态变为移动结束
        if BoardParam['is_printing']:
            BoardParam['print_steps'] = 'move end'
        else:
            for i in self.groupbox_ctrl_area.findChildren(QtWidgets.QPushButton):  # 打开相关界面操作的权限
                i.setEnabled(True)

    def myhex(n):
        return "".join(f"0x{n:08x}")

    def set_laser_freq(self, freq: str, duty: str, laser_num: int = None):
        """
        设置激光的大小
        :param laser_num:

        :param freq: 激光强度
        :return:
        """
        try:
            BoardParam['laser_dly_countdown'].stop()  # 关闭定时器
            freq = BoardParam['laser_freq'] = max(1, min(int(freq), 10000000))
            T = int((1 / freq)*1000)
            p_freq = int(50000000 / freq)
            print("freq : ", p_freq)
            #bin_p_freq = format(p_freq, '032b')
            #print("bin_b_freq : ", bin_p_freq)
            # bin_p_freq1 = bytes(bin_p_freq).encode('utf-8')
            bin_p_freq1 = p_freq.to_bytes(4, byteorder='big', signed=False)
            self.laser_serial_port.send_bytes(bin_p_freq1)
            duty1 = BoardParam['laser_duty'] = float(duty)
            p_time = int(p_freq * (1-duty1))
            #bin_p_time = format(p_time, '032b')
            #print("bin_p_time : ", bin_p_time)
            bin_p_time1 = p_time.to_bytes(4, byteorder='big', signed=False)
            self.laser_serial_port.send_bytes(bin_p_time1)
            p_num = BoardParam['laser_num'] = int(laser_num)
            Time = T * p_num
            bin_p_num = format(p_num, '08b')
            print("bin_p_num : ", bin_p_num)
            bin_p_num1 = p_num.to_bytes(1, byteorder='big', signed=False)
            self.laser_serial_port.send_bytes(bin_p_num1)
            laser_dly = laser_num / freq
            print("bin_p_dly : ", laser_dly)
            a = 0
            binary_num = a.to_bytes(1, byteorder='big', signed=False)  # 使用前缀 '0b' 表明这是一个二进制数

            self.laser_serial_port.send_bytes(binary_num)
            self.laser_serial_port.send_bytes(binary_num)

            if self.my_parent_window.laser_port_ui.checkbox_disp_send.isChecked():  # 显示内容
                self.my_parent_window.laser_port_ui.disp_data("send pwm freq : ", bin_p_freq1)
                self.my_parent_window.laser_port_ui.disp_data("send pwm time : ", bin_p_time1)
                self.my_parent_window.laser_port_ui.disp_data("send pwm num : ", bin_p_num1)
            BoardParam['laser_dly_countdown'].start(Time)
            if BoardParam['is_printing']:
                BoardParam['print_steps'] = 'in laser'

        except Exception as ep:
            self.my_parent_window.show_err(str(ep))
            traceback.print_exc()

    def stop_laser(self):
        """
        关闭激光
        :return:
        """
        self.set_laser_freq('1', '0.5', int(0))  # 发送停止指令
        BoardParam['laser_num'] = 0  # 设置当前值为0
        BoardParam['laser_dly_countdown'].stop()  # 关闭定时器

        # 如果是自动打印，现在状态变为激光结束
        if BoardParam['is_printing']:
            BoardParam['print_steps'] = 'laser end'

    def start_print(self):
        """
        开始打印（自动），主要是一些准备工作
        :return:
        """
        # if not self.checkbox_use_cfg.isChecked():
        #     # 这部分代码还没加，看需求
        #     self.my_parent_window.show_err(str("不支持该模式"))
        #     return

        if self.checkbox_use_cfg.isChecked():  # 获取自动打印配置的参数
            # 获取全局变量
            BoardParam['preset_laser_freq'] = max(1, min(int(self.lineedit_laser_freq.text()), 10000000))  # 钳制
            BoardParam['preset_laser_num'] = int(self.lineedit_laser_num.text())  # 开始倒计时
            BoardParam['preset_laser_duty'] = (self.lineedit_laser_duty.text())
            BoardParam['preset_estimated_movement_time'] = int(self.lineedit_estimated_movement_time.text())
            # BoardParam['preset_move_range_idx'][0] = max(1, self.combobox_x_move_range.currentIndex())
            BoardParam['preset_move_range_idx'][0] = self.combobox_x_move_range.currentIndex()  # 前两个不行
            BoardParam['preset_move_range_idx'][1] = self.combobox_y_move_range.currentIndex()
            # BoardParam['preset_move_range_idx'][1] = max(1, self.combobox_y_move_range.currentIndex())
            BoardParam['preset_move_range_idx'][2] = self.combobox_z_move_range.currentIndex()
        else:  # 选取默认值
            BoardParam['preset_laser_freq'] = 1
            BoardParam['preset_laser_duty'] = 0.5
            BoardParam['preset_laser_num'] = 10
            BoardParam['preset_estimated_movement_time'] = 1000
            BoardParam['preset_move_range_idx'][0] = 4  # 对应幅度100
            BoardParam['preset_move_range_idx'][1] = 4
            BoardParam['preset_move_range_idx'][2] = 4
        if not self.track_from_array_x:  # 没有轨迹
            BoardParam['is_printing'] = False
            self.my_parent_window.show_err("请读入数据")
            return
        if not self.laser_serial_port.isOpen():
            BoardParam['is_printing'] = False
            self.my_parent_window.show_err("请打开激光串口")
            return
        if not self.motor_serial_port.isOpen():
            BoardParam['is_printing'] = False
            self.my_parent_window.show_err("请打开电机串口")
            return

        # 锁定一些界面
        self.groupbox_param_cfg.setEnabled(False)
        self.groupbox_manual_ctrl.setEnabled(False)
        for i in self.groupbox_ctrl_area.findChildren(QtWidgets.QPushButton):
            i.setEnabled(False)
        self.pushbutton_stop_print.setEnabled(True)
        # ----------

        self.now_step = -1
        BoardParam['is_printing'] = True  # 开始打印标志位
        BoardParam['print_steps'] = 'move end'  # 挪到最后一个，接下来准备移动了

        self.set_laser_freq(freq=str(BoardParam['preset_laser_freq']),
                            duty=str(BoardParam['preset_laser_duty']),
                            laser_num=int(BoardParam['preset_laser_num']))

    def stop_print(self):
        """
        停止打印，直接将打印标志位归0，并关闭激光
        :return:
        """
        BoardParam['is_printing'] = False
        BoardParam['print_steps'] = None
        self.stop_laser()  # 关闭激光

        # 解锁一些界面
        self.groupbox_param_cfg.setEnabled(True)
        self.groupbox_manual_ctrl.setEnabled(True)
        for i in self.groupbox_ctrl_area.findChildren(QtWidgets.QPushButton):
            i.setEnabled(True)
        # ----------

    def auto_print(self):
        """
        自动打印函数，与定时器关联
        :return:
        """
        try:
            # 不在打印状态，退出
            if not BoardParam['is_printing']:
                return

            if BoardParam['print_steps'] == 'laser end':  # 下一步，移动
                # self.stop_laser()  # 先关闭激光
                # 更新当前步数，如果已经走完，则关闭打印
                self.now_step += 1
                if self.now_step == len(self.track_from_array_x):
                    self.stop_print()  # 完成程序了直接停止打印
                    return

                # 准备发送移动指令
                cmd = None
                # 第一步不发送移动指令，原地打印
                if self.now_step > 0:
                    # 只有在x轴坐标，或者y轴坐标发生了变化，才进行指令的更新
                    if self.track_from_array_x[self.now_step] != self.track_from_array_x[self.now_step - 1]:
                        if self.track_from_array_x[self.now_step] > self.track_from_array_x[self.now_step - 1]:
                            cmd = MOVE_CMD[0][BoardParam['preset_move_range_idx'][0]]
                        else:
                            cmd = MOVE_CMD[1][BoardParam['preset_move_range_idx'][0]]
                    elif self.track_from_array_y[self.now_step] != self.track_from_array_y[self.now_step - 1]:
                        if self.track_from_array_y[self.now_step] > self.track_from_array_y[self.now_step - 1]:
                            cmd = MOVE_CMD[2][BoardParam['preset_move_range_idx'][1]]
                        else:
                            cmd = MOVE_CMD[3][BoardParam['preset_move_range_idx'][1]]

                    self.start_motor_move(cmd, BoardParam['preset_estimated_movement_time'])  # 使用预估时间,移动电机

            elif BoardParam['print_steps'] == 'move end':
                self.set_laser_freq(freq=str(BoardParam['preset_laser_freq']),
                                    duty=str(BoardParam['preset_laser_duty']),
                                    laser_num=int(BoardParam['preset_laser_num']))  # 用预设的，不要读取

        except Exception as ep:
            self.my_parent_window.show_err(str(ep))
            traceback.print_exc()


class FigureDispUI:
    """
    轨迹图像显示区的UI代码以及对应的逻辑
    """

    class QThreadUpdateTrack(MyQThread):
        """
        线程：定时接受数据并且显示
        """
        signals = QtCore.pyqtSignal(list, list, list)

        def __init__(self):
            super().__init__()
            self.track_len = None

        def run(self):
            """
            run函数，0.1s更新
            """
            while self.is_working:
                self.msleep(300)
                if self.track_len != len(BoardParam['track_x']):
                    self.track_len = len(BoardParam['track_x'])
                    self.signals.emit(BoardParam['track_x'], BoardParam['track_y'], BoardParam['track_z'])

    def __init__(self, my_parent, groupbox_disp_figure):
        self.my_parent = my_parent
        self.groupbox_disp_figure = groupbox_disp_figure  # 用于保存画布的groupbox
        self.my_figure_canvas = MyFigureCanvas()  # 创建一个画布实例
        self.gridlayout_my_figure_canvas = QGridLayout(self.groupbox_disp_figure)  # 创建栅格布局的对象实例
        self.gridlayout_my_figure_canvas.addWidget(self.my_figure_canvas)  # 使用栅格布局，把画布嵌入到groupbox里
        start = time.time()
        self.my_figure_canvas.track_test()
        end = time.time()
        print(end - start)
        self.qthread_update_track = self.QThreadUpdateTrack()
        self.qthread_update_track.signals.connect(self.draw_track)
        self.qthread_update_track.start()

        self.my_figure_canvas.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.my_figure_canvas.customContextMenuRequested[QtCore.QPoint].connect(self.figure_canvas_right_click)

    def figure_canvas_right_click(self, pos):
        """
        显示区域的右键菜单
        :param pos:
        :return:
        """
        pop_menu = QtWidgets.QMenu()
        action_clear_editor = pop_menu.addAction('清空轨迹')

        # 获取右键菜单中当前被点击的是哪一项
        action = pop_menu.exec_(self.my_figure_canvas.mapToGlobal(pos))

        if action == action_clear_editor:
            BoardParam['motor_coord'][0] = 0
            BoardParam['motor_coord'][1] = 0
            BoardParam['motor_coord'][2] = 0
            BoardParam['track_x'].clear()
            BoardParam['track_x'].append(0)
            BoardParam['track_y'].clear()
            BoardParam['track_y'].append(0)
            BoardParam['track_z'].clear()
            BoardParam['track_z'].append(0)

    def draw_track(self, x, y, z):
        self.my_figure_canvas.draw_track(x, y, True)


class StatusBarUI:
    """
    底部状态栏的UI设计
    """

    class QThreadUpdateStatusBar(MyQThread):
        """
        线程：定时接受数据并且显示
        """

        def __init__(self):
            super().__init__()

        def run(self):
            """
            run函数，0.1s更新
            """
            while self.is_working:
                self.msleep(10)
                self.signals.emit("")

    def __init__(self, my_parent, statusbar):
        """
        # description 输入某个实例的底部状态栏
        """
        self.my_parent = my_parent

        # 显示激光开关状态
        self.label_laser_on_off = QtWidgets.QLabel()
        # 显示激光强度
        self.label_laser_freq = QtWidgets.QLabel()
        # 显示激光延迟
        self.label_laser_duty = QtWidgets.QLabel()
        # 显示激光延迟
        self.label_laser_num = QtWidgets.QLabel()
        # 实时显示激光倒计时
        self.label_laser_remaining_time = QtWidgets.QLabel()
        # 电机是否正在移动
        self.label_is_motor_moving = QtWidgets.QLabel()
        # 显示电机实际坐标
        self.label_motor_coord = QtWidgets.QLabel()

        # 写入初始值
        self.label_laser_on_off.setText("激光开关状态：")
        # 写入初始值
        self.label_laser_freq.setText("激光频率：")
        # 写入初始值
        self.label_laser_duty.setText("脉冲占空比：")
        # 写入初始值
        self.label_laser_num.setText("激光脉冲数：")
        # 写入初始值
        self.label_laser_remaining_time.setText("激光剩余时间：")
        # 写入初始值
        self.label_is_motor_moving.setText("电机是否正在移动：")
        # 写入初始值
        self.label_motor_coord.setText("电机当前坐标(um)：")

        # ? 锁定大小
        self.label_laser_on_off.setMaximumSize(QtCore.QSize(120, 20))
        self.label_laser_on_off.setMinimumSize(QtCore.QSize(120, 20))
        # ? 锁定大小
        self.label_laser_freq.setMaximumSize(QtCore.QSize(120, 20))
        self.label_laser_freq.setMinimumSize(QtCore.QSize(120, 20))
        # ? 锁定大小
        self.label_laser_duty.setMaximumSize(QtCore.QSize(120, 20))
        self.label_laser_duty.setMinimumSize(QtCore.QSize(120, 20))
        # ? 锁定大小
        self.label_laser_num.setMaximumSize(QtCore.QSize(120, 20))
        self.label_laser_num.setMinimumSize(QtCore.QSize(120, 20))
        # ? 锁定大小
        self.label_laser_remaining_time.setMaximumSize(QtCore.QSize(200, 20))
        self.label_laser_remaining_time.setMinimumSize(QtCore.QSize(200, 20))
        # ? 锁定大小
        self.label_is_motor_moving.setMaximumSize(QtCore.QSize(160, 20))
        self.label_is_motor_moving.setMinimumSize(QtCore.QSize(160, 20))
        # ? 锁定大小
        self.label_motor_coord.setMaximumSize(QtCore.QSize(480, 20))
        self.label_motor_coord.setMinimumSize(QtCore.QSize(480, 20))

        # 将元件插入
        statusbar.addPermanentWidget(self.label_laser_on_off, 1)
        # 将元件插入
        statusbar.addPermanentWidget(self.label_laser_freq, 1)
        # 将元件插入
        statusbar.addPermanentWidget(self.label_laser_duty, 2)
        # 将元件插入
        statusbar.addPermanentWidget(self.label_laser_num, 1)
        # 将元件插入
        statusbar.addPermanentWidget(self.label_laser_remaining_time, 1)
        # 将元件插入
        statusbar.addPermanentWidget(self.label_is_motor_moving, 1)
        # 将元件插入
        statusbar.addPermanentWidget(self.label_motor_coord, 1)

        self.spitter0 = QtWidgets.QSplitter()
        statusbar.addPermanentWidget(self.spitter0, 1)

        self.qthread_update_statusbar = self.QThreadUpdateStatusBar()
        self.qthread_update_statusbar.signals.connect(self.update_statusbar)
        self.qthread_update_statusbar.start()

    def update_statusbar(self):
        """
        description 若数据发生变化, 则更新一次底部状态栏
        param {*}
        return {*}
        """

        laser_on_off = '强度出错'
        if 10000000 >= BoardParam['laser_freq'] >= 0.01:
            laser_on_off = QtCore.QCoreApplication.translate("MainWindow",
                                                             "<html><head/><body><p><span style=\" font-weight:600; color:#60b53b;\">激光开关状态：开</span></p></body></html>")
        elif BoardParam['laser_num'] == 0:

            laser_on_off = QtCore.QCoreApplication.translate("MainWindow",
                                                             "<html><head/><body><p><span style=\" font-weight:600; color:#ff0000;\">激光开关状态：关</span></p></body></html>")
        self.label_laser_on_off.setText(laser_on_off)

        self.label_laser_freq.setText("激光频率：" + str(BoardParam['laser_freq']))

        self.label_laser_duty.setText("激光占空比：" + str(BoardParam['laser_duty']))

        self.label_laser_num.setText("激光脉冲数：" + str(BoardParam['laser_num']))

        if BoardParam['is_motor_moving']:
            tmp_str = QtCore.QCoreApplication.translate("MainWindow",
                                                        "<html><head/><body><p><span style=\" font-weight:600; color:#60b53b;\">电机正在移动</span></p></body></html>")
        else:
            tmp_str = QtCore.QCoreApplication.translate("MainWindow",
                                                        "<html><head/><body><p><span style=\" font-weight:600; color:#ff0000;\">电机不在移动</span></p></body></html>")
        self.label_is_motor_moving.setText(tmp_str)

        self.label_motor_coord.setText("电机当前坐标(um)：" + str(tuple(BoardParam['motor_coord'])))

        # 更新时间
        self.label_laser_remaining_time.setText(
            "激光剩余时间：" + str(BoardParam['laser_dly_countdown'].remainingTime()))


class MyWindowBasic(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    # 继承视图，增加逻辑
    # 基础的视图和逻辑
    """

    def __init__(self, parent=None):
        super(MyWindowBasic, self).__init__(parent)

        # 生成ui
        self.setupUi(self)  # 使用qt design文件生成ui
        self.resize(800, 700)  # 重新设置一下大小

        # 串口模块, 需要两个，电机和激光各一个
        self.motor_port = MySerialPort()
        self.laser_port = MySerialPort()

        # ------------------------------------------- 串口部分的UI初始化代码 ------------------------------------------
        # 电机串口相关的控件
        self.motor_port_ui = PortUI('电机', self.motor_port, self, self.portName_comboBox_2, self.bsp_comboBox_2,
                                    self.dataBit_comboBox_2,
                                    self.stopBit_comboBox_2, self.checkBit_comboBox_2, self.openPort_pushButton_2,
                                    self.refreshPort_pushButton_2, self.portName_label, self.bsp_label,
                                    self.bsp_label_7, self.bsp_label_8, self.hexDisp_checkBox_3, self.pause_checkBox_3,
                                    self.timeStamp_checkBox_3, self.clearDisp_pushButton_3, self.dataDisp_textBrowser_3,
                                    self.timeStamp_checkBox_4, self.textEdit, self.hexDisp_checkBox_6,
                                    self.pause_checkBox_6, self.clearDisp_pushButton_6, self.clearDisp_pushButton_7)
        self.motor_port_ui.ui_init()  # ui初始化

        # 激光串口控制
        self.laser_port_ui = PortUI('激光', self.laser_port, self, self.portName_comboBox_3, self.bsp_comboBox_3,
                                    self.dataBit_comboBox_3, self.stopBit_comboBox_3, self.checkBit_comboBox_3,
                                    self.openPort_pushButton_3, self.refreshPort_pushButton_3, self.portName_label_4,
                                    self.bsp_label_10, self.bsp_label_11, self.bsp_label_9, self.hexDisp_checkBox_5,
                                    self.pause_checkBox_5, self.timeStamp_checkBox_5, self.clearDisp_pushButton_5,
                                    self.dataDisp_textBrowser_5, self.timeStamp_checkBox_6, self.textEdit_2,
                                    self.hexDisp_checkBox_7, self.pause_checkBox_7, self.clearDisp_pushButton_9,
                                    self.clearDisp_pushButton_8)
        self.laser_port_ui.ui_init()  # ui初始化

        self.port_set_tabwidget = self.tabWidget
        self.disp_tabwidget = self.tabWidget_2

        self.port_set_tabwidget.setCurrentIndex(0)
        self.port_set_tabwidget.setTabText(0, '电机')
        self.port_set_tabwidget.setTabText(1, '激光')
        self.disp_tabwidget.setCurrentIndex(0)
        self.disp_tabwidget.setTabText(0, '电机')
        self.disp_tabwidget.setTabText(1, '激光')
        self.disp_tabwidget.setTabText(2, '电机串口数据发送')
        self.disp_tabwidget.setTabText(3, '激光串口数据发送')

        # ------------------------------------------- 绘制图形部分的UI初始化代码 ---------------------------------------
        self.figure_disp_ui = FigureDispUI(self, self.laserDisp_groupBox)

        # ------------------------------------------- 整个操控部分的UI初始化代码 ---------------------------------------

        self.ctrl_area_ui = CtrlAreaUI(self.motor_port, self.laser_port, self, self.groupbox_ctrl_area)

        # ------------------------------------------- 底部状态栏部分的UI初始化代码 ---------------------------------------
        self.statusbar_ui = StatusBarUI(self, self.statusbar)

        # ------------------------------------------------- 载入配置文件 ---------------------------------------------
        self.reset_config()

        self.disp_tabwidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.disp_tabwidget.customContextMenuRequested[QtCore.QPoint].connect(self.disp_tabwidget_right_click)

    # 在 MyWindowBasic 中添加处理函数
    def process_arduino_data(self, data):
        print(f"收到原始数据：{repr(data)}")
        # 解析 "POS,50.00,60.00"
        parts = data.split(',') 
        if len(parts) >= 3 and parts[0] == "POS":
            try:
                curr_x = float(parts[1])
                curr_y = float(parts[2])
                
                # 1. 更新全局坐标（用于状态栏显示）
                BoardParam['motor_coord'][0] = curr_x
                BoardParam['motor_coord'][1] = curr_y
                
                # 2. 更新轨迹列表（用于绘图）
                BoardParam['track_x'].append(curr_x)
                BoardParam['track_y'].append(curr_y)

                print(f"当前列表长度：{len(BoardParam['track_x'])}")
                
                # 3. 实时绘图
                self.figure_disp_ui.draw_track(BoardParam['track_x'], 
                                            BoardParam['track_y'],
                                            True )
            except ValueError:
                pass

    def update_motor_status(self, status):
        # 解析 "STATUS,IDLE"
        if "IDLE" in status:
            BoardParam['is_motor_moving'] = False
            # 更新状态栏显示
            self.statusbar_ui.update_statusbar()

    def disp_tabwidget_right_click(self, pos):
        """
        显示区域的右键菜单
        :param pos:
        :return:
        """
        pop_menu = QtWidgets.QMenu()
        action_clear_editor = pop_menu.addAction('清空发送栏和接收栏以及计数')

        # 获取右键菜单中当前被点击的是哪一项
        action = pop_menu.exec_(self.disp_tabwidget.mapToGlobal(pos))

        if action == action_clear_editor:
            self.motor_port_ui.clear_disp()
            self.motor_port_ui.clear_send_edit()
            self.laser_port_ui.clear_disp()
            self.laser_port_ui.clear_send_edit()

    def closeEvent(self, event):
        """
        函数名固定不可变，属于函数重构
        :param event:
        :return:
        """
        event.accept()  # 关闭窗口
        self.store_config()

    def show_err(self, err_str):
        """
        只能在主线程里调用，打印出err_str，并以弹窗的模式显示
        param {err_str 要显示的错误字符串}
        """
        # 弹出警告框
        QtWidgets.QMessageBox.warning(self, '警告', err_str)

    def store_config(self):
        pass
        # 创建一个configparser
        config = configparser.ConfigParser()

        # 主界面上要保存的
        config['motor_port_ui'] = {'combobox_baudrate': str(self.motor_port_ui.combobox_baudrate.currentIndex()),
                                   'combobox_bytesize': str(self.motor_port_ui.combobox_bytesize.currentIndex()),
                                   'combobox_stopbits': str(self.motor_port_ui.combobox_stopbits.currentIndex()),
                                   'combobox_parity': str(self.motor_port_ui.combobox_parity.currentIndex()),
                                   'checkbox_hex_disp': str(self.motor_port_ui.checkbox_hex_disp.isChecked()),
                                   'checkbox_time_stamp': str(self.motor_port_ui.checkbox_time_stamp.isChecked()),
                                   'checkbox_disp_send': str(self.motor_port_ui.checkbox_disp_send.isChecked())}

        config['laser_port_ui'] = {'combobox_baudrate': str(self.laser_port_ui.combobox_baudrate.currentIndex()),
                                   'combobox_bytesize': str(self.laser_port_ui.combobox_bytesize.currentIndex()),
                                   'combobox_stopbits': str(self.laser_port_ui.combobox_stopbits.currentIndex()),
                                   'combobox_parity': str(self.laser_port_ui.combobox_parity.currentIndex()),
                                   'checkbox_hex_disp': str(self.laser_port_ui.checkbox_hex_disp.isChecked()),
                                   'checkbox_time_stamp': str(self.laser_port_ui.checkbox_time_stamp.isChecked()),
                                   'checkbox_disp_send': str(self.motor_port_ui.checkbox_disp_send.isChecked())}

        # config['auto_ctrl_area_ui'] = {
        #     'combobox_x_move_range': str(self.auto_ctrl_area_ui.combobox_x_move_range.currentIndex()),
        #     'combobox_y_move_range': str(self.auto_ctrl_area_ui.combobox_y_move_range.currentIndex()),
        #     'combobox_z_move_range': str(self.auto_ctrl_area_ui.combobox_z_move_range.currentIndex()),
        #     'lineedit_laser_vol': str(self.auto_ctrl_area_ui.lineedit_laser_vol.text())}

        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def reset_config(self):
        if not os.path.exists("config.ini"):
            return
        config = configparser.ConfigParser()
        # 读取配置文件
        config.read('config.ini')

        self.motor_port_ui.combobox_baudrate.setCurrentIndex(int(config['motor_port_ui']['combobox_baudrate']))
        self.motor_port_ui.combobox_bytesize.setCurrentIndex(int(config['motor_port_ui']['combobox_bytesize']))
        self.motor_port_ui.combobox_stopbits.setCurrentIndex(int(config['motor_port_ui']['combobox_stopbits']))
        self.motor_port_ui.combobox_parity.setCurrentIndex(int(config['motor_port_ui']['combobox_parity']))
        self.motor_port_ui.checkbox_hex_disp.setChecked(config['motor_port_ui']['checkbox_hex_disp'] == 'True')
        self.motor_port_ui.checkbox_time_stamp.setChecked(config['motor_port_ui']['checkbox_time_stamp'] == 'True')
        self.motor_port_ui.checkbox_disp_send.setChecked(config['motor_port_ui']['checkbox_disp_send'] == 'True')

        self.laser_port_ui.combobox_baudrate.setCurrentIndex(int(config['laser_port_ui']['combobox_baudrate']))
        self.laser_port_ui.combobox_bytesize.setCurrentIndex(int(config['laser_port_ui']['combobox_bytesize']))
        self.laser_port_ui.combobox_stopbits.setCurrentIndex(int(config['laser_port_ui']['combobox_stopbits']))
        self.laser_port_ui.combobox_parity.setCurrentIndex(int(config['laser_port_ui']['combobox_parity']))
        self.laser_port_ui.checkbox_hex_disp.setChecked(config['laser_port_ui']['checkbox_hex_disp'] == 'True')
        self.laser_port_ui.checkbox_time_stamp.setChecked(config['laser_port_ui']['checkbox_time_stamp'] == 'True')
        self.laser_port_ui.checkbox_disp_send.setChecked(config['laser_port_ui']['checkbox_disp_send'] == 'True')

        # self.auto_ctrl_area_ui.combobox_x_move_range.setCurrentIndex(
        #     int(config['auto_ctrl_area_ui']['combobox_x_move_range']))
        # self.auto_ctrl_area_ui.combobox_y_move_range.setCurrentIndex(
        #     int(config['auto_ctrl_area_ui']['combobox_y_move_range']))
        # self.auto_ctrl_area_ui.combobox_z_move_range.setCurrentIndex(
        #     int(config['auto_ctrl_area_ui']['combobox_z_move_range']))
        # self.auto_ctrl_area_ui.lineedit_laser_vol.setText(config['auto_ctrl_area_ui']['lineedit_laser_vol'])


if __name__ == "__main__":
    # print(get_port_dev())
    app = QtWidgets.QApplication(sys.argv)
    myWin = MyWindowBasic()
    myWin.show()

    # hehe = MyQThread()
    # hehe.start()

    sys.exit(app.exec_())
