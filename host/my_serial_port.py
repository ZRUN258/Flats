# 新建一个串口类，增加一点新的变量，方便我使用

import serial
import serial.tools.list_ports
import traceback  # 异常处理模块
import time


def get_port_dev():
    """
    description: 获取所有的端口设备
    param {none}
    return {port_dev_list 设备列表}
    """

    port_list = list(serial.tools.list_ports.comports())  # 获取port类数组（类列表）
    port_dev_list = []  # 储存串口名称的列表

    if len(port_list) <= 0:  # 如果列表为空, 报个exception
        raise Exception("HaveNoPortErr")
    else:
        for every_port in port_list:
            port_dev_list.append(every_port.device)  # 保存所有串口名称

    return port_dev_list  # 返回列表


class MySerialPort(serial.Serial):
    """
    重新构造一个串口类，主要是增加一点收发信息，方便我使用
    """

    def __init__(self):
        """
        父类初始化
        """
        super().__init__()

        #  接受数据字节数计数
        self.rx_byte_count = 0
        #  发送数据字节数计数
        self.tx_byte_count = 0

        self.port = ''

    def set_port(self, name, baudrate, bytesize, parity, stopbits):
        """
        设置串口的初始参数
        :param name:
        :param baudrate:
        :param bytesize:
        :param parity:
        :param stopbits:
        :return:
        """
        self.port = name
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits

    def open_port(self):
        if not self.isOpen():
            # 设置超时时间
            self.timeout = 2
            # 尝试打开串口
            try:
                self.open()
                return True  # 成功返回 True
            # 如果打开失败，返回原因
            except Exception as ep:
                traceback.print_exc()
                return str(ep)  # 失败返回错误代码

    def send_bytes(self, bytes_msg=None):
        """
        发送bytes，并保存长度
        :param bytes_msg:
        :return:
        """

        now = time.localtime()
        nowt = time.strftime("%Y-%m-%d-%H_%M_%S", now)  # 这一步就是对时间进行格式化


        if bytes_msg is not None:
            # 发送数据
            self.write(bytes_msg)
            print(nowt)
            print(bytes_msg)

            # 保存长度
            self.tx_byte_count += len(bytes_msg)
