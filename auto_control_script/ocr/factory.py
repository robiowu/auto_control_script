# -*- coding: utf-8 -*-
"""
ocr/factory.py - OCR 通道工厂与对外入口模块

职责:
- 按通道名创建 OCR 引擎实例（工厂）
- 提供整图与区域识别入口，结果中标注本次实际使用的通道
- 提供通道可用状态查询

调用链:
- cli.py / script/runner.py / web/app.py -> ocr/factory.py
    -> ocr/builtin_ocr.py / ocr/precise_ocr.py / ocr/base.py

通道选择:
- auto：高精度通道可用时优先，否则使用系统内置通道
- 显式指定：前置条件缺失时直接报错，不做静默切换
"""

import logging

from typing import Optional
from auto_control_script.core.errors import ChannelUnavailableError
from auto_control_script.core.frame import Frame, crop as crop_frame
from auto_control_script.core.settings import SETTINGS

from auto_control_script.ocr.base import (
    CHANNEL_AUTO, CHANNEL_BUILTIN, CHANNEL_PRECISE, CHANNELS, BaseOcr, OcrResult,
    resolve_language,
)

logger = logging.getLogger(__name__)


def create_ocr(channel: Optional[str] = None) -> BaseOcr:
    """
    创建 OCR 引擎实例（工厂方法）。

    Args:
        channel (str): 通道名，None 时取配置默认值；
            auto 表示自动选择，builtin 为系统内置，precise 为高精度

    Returns:
        BaseOcr: 引擎实例

    Raises:
        ChannelUnavailableError: 通道名未知，或显式指定的通道不可用时抛出
    """
    engine, _reason = select_engine(channel)
    return engine


def select_engine(channel: Optional[str] = None) -> tuple:
    """
    选择 OCR 引擎，返回引擎实例与选择原因。

    Args:
        channel (str): 通道名，None 时取配置默认值

    Returns:
        tuple: (BaseOcr 引擎实例, str 选择原因)

    Raises:
        ChannelUnavailableError: 通道名未知，或显式指定的通道不可用时抛出
    """
    channel = channel or SETTINGS["ocr_channel"]
    if channel not in CHANNELS:
        raise ChannelUnavailableError(
            f"ocr.factory.select_engine: 未知 OCR 通道 {channel!r}，可选值为 {list(CHANNELS)}"
        )

    # 顺序敏感：必须先探测高精度通道，避免 winocr 先被加载后进程崩溃
    precise = _new_precise()
    builtin = _new_builtin()

    if channel == CHANNEL_AUTO:
        if precise.is_available():
            return precise, "自动选择：高精度通道可用"
        return builtin, "自动选择：高精度通道不可用，使用系统内置通道"

    if channel == CHANNEL_PRECISE:
        reason = precise.unavailable_reason()
        if reason:
            raise ChannelUnavailableError(
                f"ocr.factory.select_engine: 指定的高精度通道不可用：{reason}"
            )
        return precise, "使用者显式指定"

    reason = builtin.unavailable_reason()
    if reason:
        raise ChannelUnavailableError(
            f"ocr.factory.select_engine: 指定的系统内置通道不可用：{reason}"
        )
    return builtin, "使用者显式指定"


def _new_precise() -> BaseOcr:
    """
    构造高精度通道实例。

    Returns:
        BaseOcr: PreciseOcr 实例
    """
    from auto_control_script.ocr.precise_ocr import PreciseOcr

    return PreciseOcr()


def _new_builtin() -> BaseOcr:
    """
    构造系统内置通道实例。

    Returns:
        BaseOcr: BuiltinOcr 实例
    """
    from auto_control_script.ocr.builtin_ocr import BuiltinOcr

    return BuiltinOcr()


def channel_status() -> dict:
    """
    查询两类通道的可用状态与缺失的前置条件。

    Returns:
        dict: 含 builtin 与 precise 两个键，每个键下为
            available (bool) 与 reason (str，可用时为空)
    """
    # 顺序敏感：必须先查高精度通道，避免 winocr 先被加载后进程崩溃
    precise = _new_precise()
    builtin = _new_builtin()
    precise_reason = precise.unavailable_reason()
    builtin_reason = builtin.unavailable_reason()
    return {
        CHANNEL_BUILTIN: {
            "available": builtin_reason is None,
            "reason": builtin_reason or "",
            "languages": builtin.available_languages(),
        },
        CHANNEL_PRECISE: {
            "available": precise_reason is None,
            "reason": precise_reason or "",
        },
    }


def _sort_reading_order(items: list) -> list:
    """
    按"从上到下、每行从左到右"的阅读顺序排序。

    Args:
        items (list): TextItem 列表

    Returns:
        list: 排好序的 TextItem 列表
    """
    if not items:
        return items
    heights = [item.box[3] - item.box[1] for item in items]
    median_height = sorted(heights)[len(heights) // 2] or 1
    tolerance = max(4, int(median_height * 0.6))

    ordered = []
    current_line = []
    line_top = None
    for item in sorted(items, key=lambda value: value.box[1]):
        if line_top is None or item.box[1] - line_top <= tolerance:
            current_line.append(item)
            line_top = item.box[1] if line_top is None else line_top
        else:
            ordered.extend(sorted(current_line, key=lambda value: value.box[0]))
            current_line = [item]
            line_top = item.box[1]
    ordered.extend(sorted(current_line, key=lambda value: value.box[0]))
    for index, item in enumerate(ordered):
        item.order = index
    return ordered


def recognize(image: Frame, lang: Optional[str] = None, channel: Optional[str] = None) -> OcrResult:
    """
    对整幅画面做 OCR。

    Args:
        image (Frame): 画面帧
        lang (str): 语言名或语言标签，None 时取配置默认值
        channel (str): 通道，None 时取配置默认值；显式指定而不可用时报错

    Returns:
        OcrResult: 识别结果，含本次实际使用的通道与选择原因

    Raises:
        ChannelUnavailableError: 通道取值未知，或指定的通道不可用时抛出
    """
    engine, reason = select_engine(channel)
    language = resolve_language(lang)
    items = engine.recognize(image.pixels, language)
    logger.info(
        f"ocr.factory.recognize: 识别完成，通道={engine.channel}，"
        f"语言={language}，条目数={len(items)}，选择原因={reason}"
    )
    return OcrResult(
        items=_sort_reading_order(items),
        channel=engine.channel,
        channel_reason=reason,
        confidence_available=engine.confidence_available,
        language=language,
        region=None,
    )


def recognize_region(image: Frame, region: tuple, lang: Optional[str] = None,
                     channel: Optional[str] = None) -> OcrResult:
    """
    对画面的指定区域做 OCR，包围盒回写为原图绝对坐标。

    Args:
        image (Frame): 画面帧
        region (tuple): (x1, y1, x2, y2) 区域坐标，相对原图
        lang (str): 语言名或语言标签
        channel (str): 通道

    Returns:
        OcrResult: 识别结果，包围盒已换算为原图坐标
    """
    x1, y1, _, _ = (int(value) for value in region)
    cropped = crop_frame(image, region)
    result = recognize(cropped, lang=lang, channel=channel)
    for item in result.items:
        box_x1, box_y1, box_x2, box_y2 = item.box
        item.box = (box_x1 + x1, box_y1 + y1, box_x2 + x1, box_y2 + y1)
    result.region = tuple(int(value) for value in region)
    return result
