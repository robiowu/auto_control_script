# -*- coding: utf-8 -*-
"""
frame.py - 画面帧数据契约模块

职责:
- 定义 Frame：所有来源（Windows 三种路径、ADB）截图的统一产物
- 提供画面有效性校验、区域裁剪、保存与编码

调用链:
- capture_win.py / capture_adb.py 产出 -> frame.py -> ocr.py / matcher.py / web/app.py

坐标约定:
- Frame 的像素坐标即本项目的对外统一坐标：原点为客户区左上角，单位为图像像素
- 取图阶段已完成窗口边框裁剪与 DPI 换算，因此图像坐标可直接下发给点击动作
"""

import time
from dataclasses import dataclass, field

import cv2
import numpy

from auto_control_script.core.errors import CaptureError

ORIGIN_CLIENT_TOP_LEFT = "client-top-left"
"""str: 坐标原点说明常量，表示原点为目标客户区左上角。"""

# 像素标准差低于该值即判定为无效画面（全黑、单色、内容未渲染）
MIN_PIXEL_STD = 1.0


@dataclass
class Frame:
    """
    一次截图的统一产物，是 OCR 与模板匹配的唯一图像输入。

    Attributes:
        pixels (numpy.ndarray): BGR 顺序的像素数组，形状为 (height, width, 3)
        width (int): 图像宽度
        height (int): 图像高度
        target_id (str): 来源目标标识
        captured_at (float): 采集时刻（Unix 时间戳，秒）
        path (str): 实际使用的取图方式
        origin (str): 坐标原点说明，恒为 ORIGIN_CLIENT_TOP_LEFT
    """

    pixels: numpy.ndarray
    width: int
    height: int
    target_id: str
    captured_at: float = field(default_factory=time.time)
    path: str = "unknown"
    origin: str = ORIGIN_CLIENT_TOP_LEFT


def validate(frame: Frame) -> None:
    """
    校验画面帧是否合法且有效。

    校验内容包括维度、通道数、尺寸一致性，以及画面是否为空洞内容
    （全黑、单色、渲染未完成）。任一项不通过即报错并指明取图路径。

    Args:
        frame (Frame): 待校验的画面帧

    Raises:
        CaptureError: 维度、尺寸不合法，或画面为无效内容时抛出
    """
    pixels = frame.pixels
    if pixels is None or pixels.ndim != 3 or pixels.shape[2] != 3:
        raise CaptureError(
            f"frame.validate: 画面像素数组必须是形状为 (height, width, 3) 的三通道数组，"
            f"实际 ndim={None if pixels is None else pixels.ndim}，"
            f"shape={None if pixels is None else pixels.shape}，取图路径={frame.path}"
        )
    actual_height, actual_width = pixels.shape[:2]
    if actual_width != frame.width or actual_height != frame.height:
        raise CaptureError(
            f"frame.validate: 声明尺寸 ({frame.width}x{frame.height}) 与像素实际尺寸 "
            f"({actual_width}x{actual_height}) 不一致，取图路径={frame.path}"
        )
    if frame.width <= 0 or frame.height <= 0:
        raise CaptureError(
            f"frame.validate: 画面尺寸非法 ({frame.width}x{frame.height})，"
            f"取图路径={frame.path}，目标={frame.target_id}"
        )
    std_value = float(numpy.std(pixels))
    if std_value < MIN_PIXEL_STD:
        raise CaptureError(
            f"frame.validate: 取到的画面为无效内容（像素标准差={std_value:.3f} < "
            f"{MIN_PIXEL_STD}，通常为全黑、单色或窗口内容未渲染），"
            f"取图路径={frame.path}，目标={frame.target_id}；"
            f"可尝试改用其它取图路径，或改用前台方式让目标完成渲染"
        )


def crop(frame: Frame, region: tuple) -> Frame:
    """
    按区域裁剪画面帧，返回裁剪后的新帧（坐标仍相对原图）。

    Args:
        frame (Frame): 源画面帧
        region (tuple): (x1, y1, x2, y2) 裁剪区域，相对源图坐标

    Returns:
        Frame: 裁剪后的画面帧

    Raises:
        CaptureError: 区域越界或区域非法时抛出
    """
    x1, y1, x2, y2 = (int(value) for value in region)
    if x1 < 0 or y1 < 0 or x2 > frame.width or y2 > frame.height or x2 <= x1 or y2 <= y1:
        raise CaptureError(
            f"frame.crop: 裁剪区域 ({x1}, {y1}, {x2}, {y2}) 越界或非法，"
            f"画面尺寸为 {frame.width}x{frame.height}"
        )
    return Frame(
        pixels=frame.pixels[y1:y2, x1:x2].copy(),
        width=x2 - x1,
        height=y2 - y1,
        target_id=frame.target_id,
        captured_at=frame.captured_at,
        path=frame.path,
    )


def save(frame: Frame, filepath: str) -> None:
    """
    将画面帧保存为图片文件，格式按后缀自动识别。

    Args:
        frame (Frame): 待保存的画面帧
        filepath (str): 保存路径
    """
    cv2.imwrite(filepath, frame.pixels)


def to_jpeg_bytes(frame: Frame, quality: int = 80) -> bytes:
    """
    将画面帧编码为 JPEG 字节，供网页预览传输。

    Args:
        frame (Frame): 待编码的画面帧
        quality (int): JPEG 质量，0~100

    Returns:
        bytes: JPEG 编码后的字节内容
    """
    ok, buffer = cv2.imencode(".jpg", frame.pixels, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise CaptureError(f"frame.to_jpeg_bytes: JPEG 编码失败，画面尺寸={frame.width}x{frame.height}")
    return buffer.tobytes()


def load(filepath: str) -> Frame:
    """
    从图片文件读取画面帧，用于 OCR 等离线场景。

    Args:
        filepath (str): 图片文件路径

    Returns:
        Frame: 读取到的画面帧

    Raises:
        CaptureError: 文件不存在或无法解码时抛出
    """
    pixels = cv2.imread(filepath, cv2.IMREAD_COLOR)
    if pixels is None:
        raise CaptureError(f"frame.load: 无法读取图片文件 {filepath}（文件不存在或格式不支持）")
    height, width = pixels.shape[:2]
    return Frame(pixels=pixels, width=width, height=height, target_id="file", path="file")
