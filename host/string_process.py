"""
Description: 字符串加工处理的一些函数，方便后续的调用
version:
Author: gf
Date: 2021-01-19 23:31:34
LastEditors: gf
LastEditTime:
"""
import binascii
import re
import datetime


def purify_hexstr(ori_hexstr):
    """
    description 精华字符串，删除字符串中无关的内容, 使成为hex格式的字符串
    @sample: '0x61 0x62,0x63，0X64' >>> '61626364'
    """
    ori_hexstr = ori_hexstr.replace(' ', '')
    ori_hexstr = ori_hexstr.replace('0x', '')
    ori_hexstr = ori_hexstr.replace('0X', '')
    ori_hexstr = ori_hexstr.replace(',', '')
    ori_hexstr = ori_hexstr.replace('，', '')
    # print(id(str))
    return ori_hexstr


def hexstr_to_str(hex_str):
    """
    description 请确保输入偶数，输入hex格式的字符串，按照ascii表使其变成字符串
    @sample: '616263' >>> 'abc'
    """
    # '616263' >>> b'616263'
    hex_bytes = hex_str.encode('utf-8')
    # b'616263' >>> b'abc'
    str_bin = binascii.unhexlify(hex_bytes)
    # b'abc' >>> 'abc'
    return str_bin.decode('utf-8')


def hexstr_to_bytes(hex_str):
    """
    请确保输入偶数
    @sample: '616263' >>> b'abc'
    """
    # '616263' >>> b'616263'
    hex_bytes = hex_str.encode('utf-8')
    # b'616263' >>> b'abc'
    return binascii.unhexlify(hex_bytes)


def str_to_hexstr(string):
    '''
    字符串转为16进制字符串
    @sample: 'abc' >>> '616263'
    '''
    # 'abc' >>> b'abc'
    string_bytes = string.encode('utf-8')
    # b'abc' >>> b'616263'
    str_bin = binascii.hexlify(string_bytes)
    # b'616263' >>> '616263'
    return str_bin.decode('utf-8')


def bytes_to_hexstr(bytes):
    '''
    字符串转为16进制字符串
    @sample: 'abc' >>> '616263'
    '''
    # b'abc' >>> b'616263'
    str_bin = binascii.hexlify(bytes)
    # b'616263' >>> '616263'
    return str_bin.decode('utf-8')


def is_hexstr(string):
    """
    检测是否为hexstr
    特征：均为0~9 a~f A~F且长度为偶数
    """

    if len(string) % 2 == 0:
        temp_string = (re.search(r'\A[0-9a-fA-F]+\Z', string))
        if temp_string is not None:
            return True
    else:
        return False


def add_time_stamp(string) -> object:
    """
    description 在字符串前加上时间戳
    param {string 待加时间戳的字符串}
    """
    temp_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' : '
    #temp_time =
    return temp_time + string + '\r\n'
