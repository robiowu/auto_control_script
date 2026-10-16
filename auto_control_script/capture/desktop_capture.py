# -*- coding: utf-8 -*-
"""
capture/desktop_capture.py - Windows 整屏截图模块

职责:
- 抓取整个屏幕（虚拟屏幕，含所有显示器）的画面

调用链:
- capture/factory.py -> capture/desktop_capture.py -> core/frame.py

说明:
- 取图范围为虚拟屏幕的完整区域，坐标原点为虚拟屏幕左上角（可能为负），
  与前台点击使用的屏幕坐标一致
- 整屏取图不支持后台语义（屏幕本就是合成后的结果），故只有一条取图路径
"""

import logging

import numpy
import win32api
import win32con
import win32gui
import win32ui

from auto_control_script.capture.base import PATH_AUTO, BaseCapture
from auto_control_script.core.errors import CaptureError
from auto_control_script.core.frame import Frame
from auto_control_script.core.target import KIND_DESKTOP

PATH_DESKTOP = "desktop"
"""str: 取图路径——整屏（虚拟屏幕）GDI 拷贝。"""

SM_XVIRTUALSCREEN = 76
"""int: 系统度量项——虚拟屏幕左边界。"""

SM_YVIRTUALSCREEN = 77
"""int: 系统度量项——虚拟屏幕上边界。"""

SM_CXVIRTUALSCREEN = 78
"""int: 系统度量项——虚拟屏幕宽度。"""

SM_CYVIRTUALSCREEN = 79
"""int: 系统度量项——虚拟屏幕高度。"""

logger = logging.getLogger(__name__)


def virtual_screen() -> tuple:
    """
    取虚拟屏幕的位置与尺寸（覆盖所有显示器）。

    Returns:
        tuple: (left, top, width, height)，left/top 为虚拟屏幕左上角坐标，可能为负
    """
    return (
        win32api.GetSystemMetrics(SM_XVIRTUALSCREEN),
        win32api.GetSystemMetrics(SM_YVIRTUALSCREEN),
        win32api.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        win32api.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


class DesktopCapture(BaseCapture):
    """
    整屏截图器。

    抓取虚拟屏幕的完整区域，供「整屏」这一截图范围使用（FR-005）。
    """

    kind = KIND_DESKTOP
    paths = (PATH_AUTO, PATH_DESKTOP)

    def grab(self, target, path: str) -> Frame:
        """
        拷贝整屏像素。

        Args:
            target (Target): 目标对象（整屏目标）
            path (str): 取图路径

        Returns:
            Frame: 画面帧，坐标原点为虚拟屏幕左上角

        Raises:
            CaptureError: 屏幕尺寸非法或 GDI 拷贝失败时抛出
        """
        left, top, width, height = virtual_screen()
        if width <= 0 or height <= 0:
            raise CaptureError(
                f"capture.desktop_capture.DesktopCapture.grab: 虚拟屏幕尺寸非法 "
                f"（{width}x{height}），无法整屏取图"
            )
        desktop_dc = win32gui.GetDC(0)
        if not desktop_dc:
            raise CaptureError(
                "capture.desktop_capture.DesktopCapture.grab: GetDC(0) 失败，无法取得屏幕 DC"
            )
        try:
            mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            try:
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (left, top), win32con.SRCCOPY)
                bits = bitmap.GetBitmapBits(True)
            finally:
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
        finally:
            win32gui.ReleaseDC(0, desktop_dc)
        array = numpy.frombuffer(bits, dtype=numpy.uint8).reshape(height, width, 4)
        logger.info(
            f"capture.desktop_capture.DesktopCapture.grab: 整屏取图成功，"
            f"区域={width}x{height}，虚拟屏幕原点=({left},{top})"
        )
        return Frame(
            pixels=array[:, :, :3].copy(),
            width=width,
            height=height,
            target_id=target.id,
            path=PATH_DESKTOP,
        )
