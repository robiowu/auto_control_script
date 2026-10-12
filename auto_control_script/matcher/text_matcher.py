# -*- coding: utf-8 -*-
"""
matcher/text_matcher.py - 按字查找模块

职责:
- 基于 OCR 结果在画面中定位文字位置

调用链:
- matcher/factory.py -> matcher/text_matcher.py -> ocr/factory.py
"""

from typing import Optional
from auto_control_script.core.frame import Frame
from auto_control_script.matcher.base import KIND_TEXT, MatchResult
from auto_control_script.ocr.factory import recognize, recognize_region


def find(image: Frame, text: str, lang: Optional[str] = None, channel: Optional[str] = None,
         region: Optional[tuple] = None, exact: bool = False) -> MatchResult:
    """
    在画面中按字查找文字位置。

    Args:
        image (Frame): 待查找的画面帧
        text (str): 目标文字
        lang (str): 识别语言
        channel (str): OCR 通道
        region (tuple): 限定查找区域 (x1, y1, x2, y2)，None 表示整图
        exact (bool): True 要求文字完全相等，False 为包含匹配

    Returns:
        MatchResult: 查找结果，未命中时 found=False 且不带坐标
    """
    result = (recognize_region(image, region, lang=lang, channel=channel) if region
              else recognize(image, lang=lang, channel=channel))
    for item in result.items:
        hit = item.text == text if exact else text in item.text
        if not hit:
            continue
        x1, y1, x2, y2 = item.box
        return MatchResult(
            found=True,
            kind=KIND_TEXT,
            point=(int((x1 + x2) / 2), int((y1 + y2) / 2)),
            box=item.box,
            score=item.confidence,
            detail=f"命中文字 {item.text!r}（通道={result.channel}）",
        )
    preview = "、".join(item.text for item in result.items[:5])
    return MatchResult(
        found=False,
        kind=KIND_TEXT,
        detail=(f"未找到文字 {text!r}：识别到 {len(result.items)} 条文字"
                f"{'，前几条为：' + preview if preview else ''}（通道={result.channel}）"),
    )
