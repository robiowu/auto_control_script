# -*- coding: utf-8 -*-
"""
capture/adb_capture.py - 安卓设备截图模块

职责:
- 通过 adb exec-out screencap 获取设备屏幕，产出与其它来源一致的 Frame

调用链:
- capture/factory.py -> capture/adb_capture.py -> utils/adb.py / core/frame.py

说明:
- 使用 exec-out 而非 shell，避免标准输出的换行被转换导致 PNG 损坏
"""

import cv2
import numpy

from auto_control_script.utils import adb
from auto_control_script.capture.base import PATH_AUTO, BaseCapture
from auto_control_script.core import frame as frame_module
from auto_control_script.core.errors import CaptureError
from auto_control_script.core.frame import Frame
from auto_control_script.core.target import KIND_DEVICE

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
"""bytes: PNG 文件头魔数，用于校验截图数据是否完整。"""

PATH_ADB = "adb"
"""str: 设备取图路径标识。"""


def capture_device(serial: str) -> Frame:
    """
    截取指定安卓设备的屏幕。

    Args:
        serial (str): 设备序列号

    Returns:
        Frame: 设备屏幕画面帧，坐标原点为屏幕左上角

    Raises:
        CaptureError: 返回数据不是完整 PNG，或解码失败时抛出
    """
    data = adb.run_bytes(["exec-out", "screencap", "-p"], serial=serial)
    if not data.startswith(PNG_MAGIC):
        raise CaptureError(
            f"adb_capture.capture_device: 设备 {serial} 返回的截图不是合法 PNG，"
            f"数据前 8 字节={data[:8]!r}，数据长度={len(data)}；"
            f"常见原因是设备处于锁屏/息屏状态或 adb 输出被截断"
        )
    if not data.endswith(b"\xaeB`\x82") and b"IEND" not in data[-16:]:
        raise CaptureError(
            f"adb_capture.capture_device: 设备 {serial} 返回的 PNG 数据不完整，"
            f"数据长度={len(data)}，尾部={data[-16:]!r}"
        )
    pixels = cv2.imdecode(numpy.frombuffer(data, dtype=numpy.uint8), cv2.IMREAD_COLOR)
    if pixels is None:
        raise CaptureError(
            f"adb_capture.capture_device: 设备 {serial} 的截图解码失败，数据长度={len(data)}"
        )
    height, width = pixels.shape[:2]
    result = Frame(pixels=pixels, width=width, height=height, target_id=serial, path=PATH_ADB)
    frame_module.validate(result)
    return result


class AdbCapture(BaseCapture):
    """
    安卓设备截图器。

    Attributes:
        kind (str): 固定为 KIND_DEVICE
        paths (tuple): 支持的取图路径，auto 与 adb 等价
    """

    kind = KIND_DEVICE
    paths = (PATH_AUTO, PATH_ADB)

    def grab(self, target, path: str) -> Frame:
        """
        截取设备屏幕。

        Args:
            target (Target): 设备目标
            path (str): 取图路径，安卓侧只有 adb 一种实际实现

        Returns:
            Frame: 设备屏幕画面帧
        """
        return capture_device(target.id)
