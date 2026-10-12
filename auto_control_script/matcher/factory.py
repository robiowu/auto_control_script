# -*- coding: utf-8 -*-
"""
matcher/factory.py - 查找能力对外入口模块

职责:
- 提供按图查找与按字查找两个入口，统一返回可直接点击的坐标

调用链:
- cli.py / script/runner.py / web/app.py / case.py -> matcher/factory.py
    -> matcher/image_matcher.py / matcher/text_matcher.py
"""

from typing import Optional, Union

import numpy

from auto_control_script.core.frame import Frame
from auto_control_script.matcher.base import MatchResult
from auto_control_script.matcher.image_matcher import DEFAULT_THRESHOLD


def find_by_image(image: Frame, template: Union[str, numpy.ndarray, Frame],
                  threshold: float = DEFAULT_THRESHOLD, is_gray: bool = True) -> MatchResult:
    """
    在画面中按图查找模板位置。

    Args:
        image (Frame): 待查找的画面帧
        template (str | numpy.ndarray | Frame): 模板
        threshold (float): 相似度阈值，越接近 1 越严格
        is_gray (bool): 是否转灰度匹配

    Returns:
        MatchResult: 查找结果，未命中时 found=False 且不带坐标

    Raises:
        CaptureError: 模板大于画面或模板为空时抛出
    """
    from auto_control_script.matcher.image_matcher import find

    return find(image, template, threshold=threshold, is_gray=is_gray)


def find_by_text(image: Frame, text: str, lang: Optional[str] = None, channel: Optional[str] = None,
                 region: Optional[tuple] = None, exact: bool = False) -> MatchResult:
    """
    在画面中按字查找文字位置。

    Args:
        image (Frame): 待查找的画面帧
        text (str): 目标文字
        lang (str): 识别语言
        channel (str): OCR 通道
        region (tuple): 限定查找区域，None 表示整图
        exact (bool): True 要求文字完全相等，False 为包含匹配

    Returns:
        MatchResult: 查找结果，未命中时 found=False 且不带坐标
    """
    from auto_control_script.matcher.text_matcher import find

    return find(image, text, lang=lang, channel=channel, region=region, exact=exact)
