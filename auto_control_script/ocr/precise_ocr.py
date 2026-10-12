# -*- coding: utf-8 -*-
"""
ocr/precise_ocr.py - 高精度 OCR 通道模块

职责:
- 基于 onnxruntime 推理的 PP-OCRv4 模型完成识别，精度显著高于系统内置通道
- 引擎构造昂贵，进程内缓存复用

调用链:
- ocr/factory.py -> ocr/precise_ocr.py -> rapidocr_onnxruntime

说明:
- 本通道为可选依赖，未安装时 is_available() 返回 False，
  由 factory 决定改用系统内置通道或按显式指定报错
"""

import importlib.util

from auto_control_script.core.errors import ChannelUnavailableError
from auto_control_script.ocr.base import CHANNEL_PRECISE, BaseOcr, TextItem

INSTALL_COMMAND = "pip install rapidocr-onnxruntime onnxruntime"
"""str: 启用高精度通道的安装命令。"""

_engine = None
"""引擎单例，首次识别时构造。"""

_loaded = False
"""bool: rapidocr_onnxruntime 是否已在当前进程中完成导入。"""


class PreciseOcr(BaseOcr):
    """
    高精度 OCR 通道。

    Attributes:
        channel (str): 固定为 CHANNEL_PRECISE
        confidence_available (bool): 固定为 True，返回真实置信度
    """

    channel = CHANNEL_PRECISE
    confidence_available = True

    @staticmethod
    def preload() -> bool:
        """
        若已安装则提前导入本通道依赖，返回是否已导入。

        存在环境级的加载顺序冲突：先导入 winocr（系统内置通道）再导入 onnxruntime
        会导致进程直接崩溃（访问冲突，无法被异常捕获）。因此任何可能加载 winocr
        的路径，都应先调用本方法把高精度通道的底层库导入进来。

        Returns:
            bool: 已安装并导入成功返回 True，未安装返回 False
        """
        global _loaded
        if _loaded:
            return True
        if importlib.util.find_spec("rapidocr_onnxruntime") is None:
            return False
        PreciseOcr._import_rapidocr()
        return True

    @staticmethod
    def _import_rapidocr():
        """
        导入 rapidocr_onnxruntime 并取得引擎类。

        Returns:
            type: RapidOCR 引擎类

        Raises:
            ChannelUnavailableError: 依赖未安装时抛出
        """
        global _loaded
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as error:
            raise ChannelUnavailableError(
                f"ocr.precise_ocr.PreciseOcr._import_rapidocr: 未安装高精度 OCR 通道依赖；"
                f"执行 `{INSTALL_COMMAND}` 后可启用（会下载 PP-OCRv4 模型，约百 MB）"
            ) from error
        _loaded = True
        return RapidOCR

    def unavailable_reason(self) -> str:
        """
        获取高精度通道不可用的原因。

        Returns:
            str: 可用时返回 None，不可用时返回说明缺失什么的字符串
        """
        if PreciseOcr.preload():
            return None
        return (
            f"未安装高精度 OCR 通道依赖；执行 `{INSTALL_COMMAND}` 后可启用"
            f"（会下载 PP-OCRv4 模型，约百 MB）"
        )

    def get_engine(self):
        """
        获取（必要时构造）高精度识别引擎。

        Returns:
            RapidOCR: 识别引擎实例

        Raises:
            ChannelUnavailableError: 依赖未安装时抛出
        """
        global _engine
        if _engine is not None:
            return _engine
        engine_class = PreciseOcr._import_rapidocr()
        _engine = engine_class()
        return _engine

    def recognize(self, pixels, language: str) -> list:
        """
        用高精度通道识别图像。

        Args:
            pixels (numpy.ndarray): BGR 顺序的像素数组
            language (str): 语言标签，本通道由模型决定语言，该参数不使用

        Returns:
            list: TextItem 列表，含真实置信度

        Raises:
            ChannelUnavailableError: 依赖未安装时抛出
        """
        engine = self.get_engine()
        result, _elapse = engine(pixels)
        items = []
        if not result:
            return items
        for box_points, text, score in result:
            x_values = [point[0] for point in box_points]
            y_values = [point[1] for point in box_points]
            items.append(TextItem(
                text=str(text).strip(),
                box=(int(min(x_values)), int(min(y_values)),
                     int(max(x_values)), int(max(y_values))),
                confidence=float(score),
            ))
        return items
