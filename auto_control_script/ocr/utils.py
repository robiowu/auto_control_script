# -*- coding: utf-8 -*-
"""
ocr/utils.py - 结构化信息提取模块

职责:
- 从识别出的文本中提取数字、金额、时间、百分比

调用链:
- ocr/factory.py -> ocr/utils.py -> re

说明:
- 提取不到时返回 None，不返回 0 等易被误认为有效值的哨兵值
"""

import re
from typing import Union

EXTRACT_NUMBER = "number"
"""str: 提取数字。"""

EXTRACT_AMOUNT = "amount"
"""str: 提取金额（带千分位）。"""

EXTRACT_TIME = "time"
"""str: 提取时间。"""

EXTRACT_PERCENTAGE = "percentage"
"""str: 提取百分比。"""

EXTRACT_KINDS = (EXTRACT_NUMBER, EXTRACT_AMOUNT, EXTRACT_TIME, EXTRACT_PERCENTAGE)
"""tuple: 结构化提取支持的类型。"""


def extract(text: str, kind: str) -> Union[float, str, None]:
    """
    从识别文本中提取结构化信息，无法提取时返回 None。

    Args:
        text (str): 待提取的文本
        kind (str): number / amount / time / percentage

    Returns:
        float | str | None: number 与 percentage 返回 float，time 返回 "HH:MM"
            形式的字符串，无法提取时返回 None

    Raises:
        ValueError: kind 取值非法时抛出
    """
    if kind not in EXTRACT_KINDS:
        raise ValueError(
            f"ocr.utils.extract: 未知提取类型 {kind!r}，可选值为 {list(EXTRACT_KINDS)}"
        )
    if kind == EXTRACT_TIME:
        match = re.search(r"(\d{1,2})\s*[:：]\s*(\d{2})", text)
        if not match:
            return None
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    if kind == EXTRACT_PERCENTAGE:
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
        return float(match.group(1)) if match else None
    if kind == EXTRACT_AMOUNT:
        match = re.search(r"[-+]?\d[\d,，]*(?:\.\d+)?", text)
        if not match:
            return None
        return float(match.group(0).replace(",", "").replace("，", ""))
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None
