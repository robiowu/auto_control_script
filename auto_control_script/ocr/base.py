# -*- coding: utf-8 -*-
"""
ocr/base.py - OCR 通道抽象基类与输出结构模块

职责:
- 定义 TextItem / OcrResult 两个输出结构
- 定义 BaseOcr 抽象基类，约定通道必须实现的三件事
- 提供语言名解析

调用链:
- ocr/factory.py -> ocr/base.py -> core/settings.py
- ocr/builtin_ocr.py / ocr/precise_ocr.py -> ocr/base.py

坐标约定:
- TextItem.box 恒相对输入图像；区域识别时由 factory 回写为原图绝对坐标
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing import Optional
from auto_control_script.core.settings import SETTINGS

CHANNEL_AUTO = "auto"
"""str: 自动选择通道（高精度可用时优先）。"""

CHANNEL_BUILTIN = "builtin"
"""str: 系统内置 OCR 通道。"""

CHANNEL_PRECISE = "precise"
"""str: 高精度 OCR 通道。"""

CHANNELS = (CHANNEL_AUTO, CHANNEL_BUILTIN, CHANNEL_PRECISE)
"""tuple: 全部合法的通道取值。"""

LANGUAGE_MAP = {
    "ch": "zh-Hans-CN",
    "zh": "zh-Hans-CN",
    "zh-cn": "zh-Hans-CN",
    "chinese": "zh-Hans-CN",
    "en": "en-US",
    "eng": "en-US",
    "english": "en-US",
}
"""dict: 简写语言名到 Windows OCR 语言标签的映射。"""


@dataclass
class TextItem:
    """
    OCR 输出的一条文字。

    Attributes:
        text (str): 识别出的文字
        box (tuple): (x1, y1, x2, y2) 包围盒，相对输入图像
        confidence (float): 置信度；系统内置通道不提供置信度，取值为 None
        order (int): 阅读顺序序号，从 0 开始
    """

    text: str
    box: tuple
    confidence: Optional[float] = None
    order: int = 0


@dataclass
class OcrResult:
    """
    一次 OCR 调用的整体结果。

    Attributes:
        items (list): 按阅读顺序排列的 TextItem 列表
        channel (str): 本次实际使用的通道
        channel_reason (str): 为何选该通道
        confidence_available (bool): 该通道是否提供真实置信度
        language (str): 使用的语言标签
        region (tuple): 识别区域，None 表示整图
    """

    items: list = field(default_factory=list)
    channel: str = CHANNEL_BUILTIN
    channel_reason: str = ""
    confidence_available: bool = False
    language: str = ""
    region: Optional[tuple] = None

    @property
    def text(self) -> str:
        """str: 全部文字按阅读顺序拼接的结果，以换行分隔。"""
        return "\n".join(item.text for item in self.items)


class BaseOcr(ABC):
    """
    OCR 通道抽象基类。

    子类需声明两个类属性并实现两个抽象方法，工厂据此做可用性与通道选择。

    Attributes:
        channel (str): 通道标识，取 CHANNEL_* 之一
        confidence_available (bool): 本通道是否返回真实置信度
    """

    channel: str = ""
    """str: 通道标识，子类覆盖。"""

    confidence_available: bool = False
    """bool: 是否返回真实置信度，子类覆盖。"""

    @abstractmethod
    def unavailable_reason(self) -> str:
        """
        获取本通道不可用的原因。

        Returns:
            str: 可用时返回 None，不可用时返回说明缺失什么的字符串
        """

    @abstractmethod
    def recognize(self, pixels, language: str) -> list:
        """
        识别图像中的文字。

        Args:
            pixels (numpy.ndarray): BGR 顺序的像素数组
            language (str): 语言标签

        Returns:
            list: TextItem 列表
        """

    def is_available(self) -> bool:
        """
        判断本通道是否可用。

        Returns:
            bool: 可用返回 True
        """
        return self.unavailable_reason() is None


def resolve_language(lang: str) -> str:
    """
    把简写语言名解析为 Windows OCR 语言标签。

    Args:
        lang (str): 语言名或已是语言标签

    Returns:
        str: 语言标签，如 "zh-Hans-CN"
    """
    if lang is None:
        lang = SETTINGS["ocr_language"]
    return LANGUAGE_MAP.get(str(lang).strip().lower(), lang)
