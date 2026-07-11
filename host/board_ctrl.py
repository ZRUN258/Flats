# 存放与控制开发板有关的代码，比如指令、通信之类的
import traceback
import numpy as np
from PyQt5 import QtCore

from my_serial_port import MySerialPort

STEP_SIZE = [2, 5, 10, 50, 100, 1000, 15000]

# # 2 5 10 50 100 um
# XP_CMD = [None, None, b'a5', b'c5', b'c1']
# XN_CMD = [None, None, b'b5', b'd5', b'd1']
# YP_CMD = [None, None, b'a6', b'c6', b'c2']
# YN_CMD = [None, None, b'b6', b'd6', b'd2']
# ZP_CMD = [b'c9', b'c8', b'a7', b'c7', b'c3']
# ZN_CMD = [b'd9', b'd8', b'b7', b'd7', b'd3']

BoardParam = {
    # 这里的是常规参数，对应的是实际用的值
    'laser_freq': 0,  # 目前的激光强队
    'laser_duty': 0.5,  # 目前的激光延迟总大小
    'laser_num': 10,  # 目前的激光延迟总大小
    'laser_dly_countdown': QtCore.QTimer(),  # 激光倒计时
    'moving_countdown': QtCore.QTimer(),  # 移动倒计时
    'motor_coord': [0, 0, 0],  # 电机目前所在的坐标
    'track_x': [0],
    'track_y': [0],
    'track_z': [0],  # 坐标轨迹，三个的大小是一样的，合起来就是每一个三维坐标
    'estimated_movement_time': 50,  # 当前采用的步伐
    'is_motor_moving': False,  # 记录，电机是否在移动过程中
    'is_printing': False,  # 记录，是否正在自动打印中
    'print_steps': None,  # 记录当前自动打印的步骤，None 'in move' 'move end' 'in laser' 'laser end'

    # 下面的用来预设参数，用来自动打印的
    'preset_laser_vol': 0,
    'preset_laser_dly': 0,
    'preset_move_range_idx': [0, 0, 0],  # 预设的xyz三轴对应的步幅
    'preset_estimated_movement_time': 50,
}

# # 移动指令 X+ X- Y+ Y- Z+ Z-，矩阵格式方便找到步幅
MOVE_CMD = np.array([[b'a1', b'a2', b'a3', b'a4', b'a5', b'a6', b'a7'],
                     [b'b1', b'b2', b'b3', b'b4', b'b5', b'b6', b'b7'],
                     [b'c1', b'c2', b'c3', b'c4', b'c5', b'c6', b'c7'],
                     [b'd1', b'd2', b'd3', b'd4', b'd5', b'd6', b'd7'],
                     [b'e1', b'e2', b'e3', b'e4', b'e5', b'e6', b'e7'],
                     [b'f1', b'f2', b'f3', b'f4', b'f5', b'f6', b'f7']])


'''
1-15
MOVE_CMD = np.array([[b'a3', b'b3', b'a1', b'a5', b'c5', b'a8', b'c1'],
                     [b'b1', b'd8', b'b1', b'b5', b'd5', b'b8', b'd1'],
                     [b'a3', b'b3', b'a1', b'a5', b'c5', b'a8', b'c1'],
                     [b'a3', b'b3', b'a1', b'a5', b'c5', b'a8', b'c1'],
                     [b'a3', b'a4', b'c10', b'a7', b'c7', b'c3', b'c9'],
                     [b'b3', b'b4', b'd10', b'b7', b'd7', b'd3', b'd9']])


原始
MOVE_CMD = np.array([[b'a3', b'b3', b'c1', b'a5', b'c5', b'a8', b'c1'],
                     [b'b1', b'd8', b'd1', b'b5', b'd5', b'b8', b'd1'],
                     [b'a3', b'b3', b'c2', b'a6', b'c6', b'a8', b'c1'],
                     [b'a3', b'b3', b'd2', b'b6', b'd6', b'a8', b'c1'],
                     [b'a3', b'a4', b'c10', b'a7', b'c7', b'c3', b'c9'],
                     [b'b3', b'b4', b'd10', b'b7', b'd7', b'd3', b'd9']])

'''
# # 移动指令 X+ X- Y+ Y- Z+ Z-，矩阵格式方便找到步幅
"""
MOVE_CMD = np.array([[b'b3', b'a3', b'a5', b'c5', b'c1'],
                      [b'b1', b'd8', b'b5', b'd5', b'd1'],
                      [b'b3', b'a3', b'a5', b'c5', b'c1'],
                      [b'b3', b'a3', b'a5', b'c5', b'c1'],
                      [b'a3', b'c10', b'a7', b'c7', b'c3'],
                      [b'b3', b'd10', b'b7', b'd7', b'd3']])



MOVE_CMD = np.array([[b'a1', b'c8', b'a5', b'c5', b'c1'],
                      [b'b1', b'd8', b'b5', b'd5', b'd1'],
                      [b'a2', b'c9', b'a6', b'c6', b'c2'],
                      [b'b2', b'd9', b'b6', b'd6', b'd2'],
                      [b'a3', b'c10', b'a7', b'c7', b'c3'],
                      [b'b3', b'd10', b'b7', b'd7', b'd3']])
"""


# 移动指令 XP XN YP YN ZP ZN，矩阵格式方便找到步幅
# MOVE_CMD = np.array([[None, None, b'\xa5', b'\xc5', b'\xc1'],
#                     [None, None, b'\xb5', b'\xd5', b'\xd1'],
#                     [None, None, b'\xa6', b'\xc6', b'\xc2'],
#                     [None, None, b'\xb6', b'\xd6', b'\xd2'],
#                     [b'\xc9', b'\xc8', b'\xa7', b'\xc7', b'\xc3'],
#                     [b'\xd9', b'\xd8', b'\xb7', b'\xd7', b'\xd3']])

# # 板子上会用到的参数
# BoardParam = {'now_laser_vol': 0,  # 板子上当前激光强度，这个是用来显示的
#               'tgt_laser_vol': 0,  # 期望的目标的激光强度
#               'tgt_laser_dly': 0,  # 完整的激光延迟
#               'laser_dly_countdown': QtCore.QTimer(),  # 激光倒计时
#               'moving_countdown': QtCore.QTimer(),  # 移动倒计时
#               'now_motor_coord': [0, 0, 0],  # 电机目前所在的坐标
#               'track_x': [0],
#               'track_y': [0],
#               'track_z': [0],  # 坐标轨迹，三个的大小是一样的，合起来就是每一个三维坐标
#               'is_motor_moving': False,  # 记录，电机是否在移动过程中
#               'is_printing': False,  # 是否正在自动打印？
#               'move_range_idx': [0, 0, 0],  # xyz三轴
#               'estimated_movement_time': 50,  # 这个算是tgt的
#               'now_print_step': None  # None 'in move' 'move end' 'in laser' 'laser end'
#               }
# # 方便全局使用
# NowLaserVol = [0]
# TgtLaserVol = [0]
# NowLaserDly = [0]
# NowMotorCoord = [0, 0, 0]
# Track_X = [0]
# Track_Y = [0]
# Track_Z = [0]
#
# IsMotorMoving = [False]  # 电机是否正在移动，全局变量方便显示在底部状态栏
# LaserCountDown = QtCore.QTimer()  # 仅用于记录激光倒计时
# LaserCountDown.timeout.connect(lambda: print('i am working'))


def read_track_xlsx(file_path):
    """
    读取xlsx文件, file_path是字符串
    :param file_path:
    :return:
    """
    pass

    csv_array = np.loadtxt(file_path,
                           dtype=int,
                           delimiter=',',
                           unpack=True,
                           skiprows=0)  # 指定读取时忽略的行数，默认从首行开始计数
    return csv_array


def get_track_from_array(csv_array):
    """
    获取轨迹，蛇字形，用于获取矩形轨迹没有问题
    :return:
    """

    if type(csv_array) != np.ndarray:
        return [], []
    track_from_array_x = []
    track_from_array_y = []
    array_shape = csv_array.shape  # 获取形状
    for i in range(array_shape[0]):
        if i % 2 == 0:
            j_range = range(array_shape[1])
        else:
            j_range = range(array_shape[1] - 1, -1, -1)
        for j in j_range:
            track_from_array_x.append(i)
            track_from_array_y.append(j)
    return track_from_array_x, track_from_array_y  # 返回轨迹坐标


if __name__ == '__main__':
    read_track_xlsx(r'xyz.csv')
