# -*- coding: utf-8 -*-
"""
matcher/base.py - 查找结果数据契约模块

职责:
- 定义 MatchResult：一次查找的统一结果

调用链:
- matcher/factory.py -> matcher/base.py

约定:
- 未命中时 point 与 box 均为 None，不给出坐标，避免调用方误用
"""

from dataclasses import dataclass
from typing import Optional

KIND_IMAGE = "image"
"""str: 查找方式——按图。"""

KIND_TEXT = "text"
"""str: 查找方式——按字。"""


@dataclass
class MatchResult:
    """
    一次查找的结果。

    Attributes:
        found (bool): 是否命中
        kind (str): 查找方式，KIND_IMAGE 或 KIND_TEXT
        point (tuple): 可直接用于点击的中心坐标 (x, y)，未命中为 None
        box (tuple): 命中区域 (x1, y1, x2, y2)，未命中为 None
        score (float): 置信度；按字查找时若通道不提供置信度则为 None
        detail (str): 补充说明，未命中时为未命中原因
    """

    found: bool
    kind: str
    point: Optional[tuple] = None
    box: Optional[tuple] = None
    score: Optional[float] = None
    detail: str = ""
