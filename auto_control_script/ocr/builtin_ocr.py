# -*- coding: utf-8 -*-
"""
ocr/builtin_ocr.py - 系统内置 OCR 通道模块

职责:
- 调用 Windows 系统 OCR 完成识别，零模型下载、开箱即用
- 校验所需语言包是否已安装，缺失时给出确切的安装命令

调用链:
- ocr/factory.py -> ocr/builtin_ocr.py -> winocr / cv2 / PIL

限制（原样暴露，不伪造数据）:
- 系统 OCR 不返回逐条置信度，本通道的 TextItem.confidence 恒为 None，
  由 confidence_available=False 告知调用方

加载顺序:
- 必须先导入高精度通道的底层库，原因见 precise_ocr.preload 的说明
"""

import asyncio

import cv2
from PIL import Image

from auto_control_script.core.errors import ChannelUnavailableError
from auto_control_script.ocr.base import CHANNEL_BUILTIN, BaseOcr, TextItem

LANGUAGE_INSTALL_HINT = (
    "以管理员身份在 PowerShell 中执行："
    "Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\""
)
"""str: 缺失 Windows OCR 语言包时的安装命令模板。"""

_loop = None
"""asyncio.AbstractEventLoop: 内置通道复用的事件循环，首次识别时创建。"""


def _get_loop() -> asyncio.AbstractEventLoop:
    """
    获取内置通道复用的事件循环，未创建或已关闭时新建并设为当前。

    系统 OCR 的异步接口需要一个事件循环；每次识别新建循环会累积未关闭的循环，
    故在整个进程内固定复用同一个。

    Returns:
        asyncio.AbstractEventLoop: 可复用的事件循环
    """
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


class BuiltinOcr(BaseOcr):
    """
    系统内置 OCR 通道。

    Attributes:
        channel (str): 固定为 CHANNEL_BUILTIN
        confidence_available (bool): 固定为 False，系统 OCR 不返回置信度
    """

    channel = CHANNEL_BUILTIN
    confidence_available = False

    def _import_winocr(self):
        """
        导入 winocr 及其 Language / OcrEngine。

        Returns:
            tuple: (winocr 模块, Language 类, OcrEngine 类)

        Raises:
            ChannelUnavailableError: winocr 未安装时抛出
        """
        # 必须先加载高精度通道的底层库，否则进程会崩溃
        from auto_control_script.ocr.precise_ocr import PreciseOcr

        PreciseOcr.preload()
        try:
            import winocr
            from winocr import Language, OcrEngine
        except ImportError as error:
            raise ChannelUnavailableError(
                f"ocr.builtin_ocr.BuiltinOcr._import_winocr: 系统内置通道依赖 winocr，"
                f"当前环境未安装；执行 `pip install winocr` 后可启用，"
                f"或改用高精度通道（pip install rapidocr-onnxruntime onnxruntime）"
            ) from error
        return winocr, Language, OcrEngine

    def unavailable_reason(self) -> str:
        """
        判断系统内置通道是否可用。

        Returns:
            str: 可用时返回 None，不可用时返回说明缺失什么的字符串
        """
        try:
            self._import_winocr()
        except ChannelUnavailableError as error:
            return str(error)
        return None

    def available_languages(self) -> list:
        """
        列出系统已安装的 OCR 语言标签。

        Returns:
            list: 语言标签列表，如 ["zh-Hans-CN"]；通道不可用时返回空列表
        """
        try:
            _winocr, _language, engine_class = self._import_winocr()
        except ChannelUnavailableError:
            return []
        return [item.language_tag for item in engine_class.available_recognizer_languages]

    def _ensure_language(self, lang: str) -> str:
        """
        校验语言包已安装。

        Args:
            lang (str): Windows OCR 语言标签

        Returns:
            str: 校验通过的语言标签

        Raises:
            ChannelUnavailableError: 语言包未安装时抛出，消息含安装命令
        """
        self._import_winocr()
        installed = self.available_languages()
        if lang in installed:
            return lang
        if not installed:
            raise ChannelUnavailableError(
                f"ocr.builtin_ocr.BuiltinOcr._ensure_language: 系统未安装任何 OCR 语言包，"
                f"无法使用系统内置通道；请先安装语言包，例如中文："
                f"Add-WindowsCapability -Online -Name \"Language.OCR~~~zh-Hans-CN~0.0.1.0\"，"
                f"或改用高精度通道（pip install rapidocr-onnxruntime onnxruntime）"
            )
        raise ChannelUnavailableError(
            f"ocr.builtin_ocr.BuiltinOcr._ensure_language: 系统未安装 OCR 语言包 {lang!r}，"
            f"已安装的语言包为 {installed}；"
            f"安装命令：" + LANGUAGE_INSTALL_HINT.format(tag=lang) +
            f"，或把识别语言改为已安装的语言，或改用高精度通道"
        )

    def recognize(self, pixels, language: str) -> list:
        """
        用系统 OCR 识别图像。

        Args:
            pixels (numpy.ndarray): BGR 顺序的像素数组
            language (str): Windows OCR 语言标签

        Returns:
            list: TextItem 列表，置信度恒为 None

        Raises:
            ChannelUnavailableError: 语言包缺失或识别失败时抛出
        """
        winocr, _language_class, _engine_class = self._import_winocr()
        self._ensure_language(language)
        rgb = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
        result = _get_loop().run_until_complete(
            winocr.recognize_pil(pil_image, lang=language))

        items = []
        for line in result.get("lines", []):
            text = (line.get("text") or "").strip()
            if not text:
                continue
            boxes = []
            for word in line.get("words", []):
                rect = word.get("bounding_rect") or {}
                if "x" not in rect:
                    continue
                boxes.append((
                    int(rect["x"]), int(rect["y"]),
                    int(rect["x"] + rect["width"]), int(rect["y"] + rect["height"]),
                ))
            if not boxes:
                continue
            box = (
                min(item[0] for item in boxes),
                min(item[1] for item in boxes),
                max(item[2] for item in boxes),
                max(item[3] for item in boxes),
            )
            items.append(TextItem(text=text, box=box, confidence=None))
        return items
