# -*- coding: utf-8 -*-
"""
matcher/image_matcher.py - 按图查找模块

职责:
- 用 OpenCV 模板匹配在画面中定位模板图

调用链:
- matcher/factory.py -> matcher/image_matcher.py -> cv2 / core/frame.py
"""

from typing import Union

import cv2
import numpy

from auto_control_script.core.errors import CaptureError
from auto_control_script.core.frame import Frame, load as load_frame
from auto_control_script.matcher.base import KIND_IMAGE, MatchResult

DEFAULT_THRESHOLD = 0.95
"""float: 模板匹配的默认相似度阈值。"""


def _template_to_array(template: Union[str, numpy.ndarray, Frame]) -> numpy.ndarray:
    """
    把模板参数统一转换为 BGR 像素数组。

    Args:
        template (str | numpy.ndarray | Frame): 模板图片路径、像素数组或画面帧

    Returns:
        numpy.ndarray: BGR 顺序的模板像素数组

    Raises:
        CaptureError: 类型不支持或文件无法读取时抛出
    """
    if isinstance(template, Frame):
        return template.pixels
    if isinstance(template, numpy.ndarray):
        return template
    if isinstance(template, str):
        return load_frame(template).pixels
    raise CaptureError(
        f"matcher.image_matcher._template_to_array: 不支持的模板类型 "
        f"{type(template).__name__}，可选类型为 图片路径(str)、像素数组(numpy.ndarray) "
        f"或 画面帧(Frame)"
    )


def find(image: Frame, template: Union[str, numpy.ndarray, Frame],
         threshold: float = DEFAULT_THRESHOLD, is_gray: bool = True) -> MatchResult:
    """
    在画面中按图查找模板位置。

    Args:
        image (Frame): 待查找的画面帧
        template (str | numpy.ndarray | Frame): 模板
        threshold (float): 相似度阈值，越接近 1 越严格
        is_gray (bool): 是否转灰度匹配，默认 True（更快）

    Returns:
        MatchResult: 查找结果，未命中时 found=False 且不带坐标

    Raises:
        CaptureError: 模板大于画面或模板为空时抛出
    """
    template_pixels = _template_to_array(template)
    template_height, template_width = template_pixels.shape[:2]
    if template_height == 0 or template_width == 0:
        raise CaptureError(
            f"matcher.image_matcher.find: 模板尺寸为 {template_width}x{template_height}，"
            f"无法匹配"
        )
    if template_height > image.height or template_width > image.width:
        raise CaptureError(
            f"matcher.image_matcher.find: 模板尺寸 {template_width}x{template_height} "
            f"大于画面 {image.width}x{image.height}，无法匹配"
        )

    if is_gray:
        source = cv2.cvtColor(image.pixels, cv2.COLOR_BGR2GRAY)
        pattern = cv2.cvtColor(template_pixels, cv2.COLOR_BGR2GRAY)
    else:
        source = image.pixels
        pattern = template_pixels
    result = cv2.matchTemplate(source, pattern, cv2.TM_CCOEFF_NORMED)
    _, max_value, _, max_location = cv2.minMaxLoc(result)

    if max_value < threshold:
        return MatchResult(
            found=False,
            kind=KIND_IMAGE,
            score=float(max_value),
            detail=f"未找到匹配图片：最佳相似度 {max_value:.4f} 低于阈值 {threshold}",
        )
    x, y = max_location
    box = (int(x), int(y), int(x + template_width), int(y + template_height))
    return MatchResult(
        found=True,
        kind=KIND_IMAGE,
        point=(int(x + template_width / 2), int(y + template_height / 2)),
        box=box,
        score=float(max_value),
        detail=f"命中相似度 {max_value:.4f}",
    )
