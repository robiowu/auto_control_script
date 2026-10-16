# -*- coding: utf-8 -*-
"""
capture/factory.py - 截图器工厂与对外入口模块

职责:
- 按目标类型创建对应平台的截图器（工厂）
- 提供整图、区域、保存、释放四个对外入口

调用链:
- cli.py / script/runner.py / web/app.py / case.py -> capture/factory.py
    -> capture/window_capture.py / capture/adb_capture.py / core/frame.py
"""

import logging

from typing import Optional
from auto_control_script.capture.base import BaseCapture
from auto_control_script.core import target as target_module
from auto_control_script.core.frame import Frame, save as save_frame, crop as crop_frame
from auto_control_script.core.settings import SETTINGS
from auto_control_script.core.target import Target

logger = logging.getLogger(__name__)

def create_capture(target_kind: str) -> BaseCapture:
    """
    按目标类型创建截图器（工厂方法）。

    Args:
        target_kind (str): 目标类型，取 core.target.KIND_WINDOW 或 KIND_DEVICE

    Returns:
        BaseCapture: 平台截图器实例

    Raises:
        ChannelUnavailableError: 目标类型非法时抛出
    """
    if target_kind == target_module.KIND_WINDOW:
        from auto_control_script.capture.window_capture import WindowCapture

        return WindowCapture()
    if target_kind == target_module.KIND_DEVICE:
        from auto_control_script.capture.adb_capture import AdbCapture

        return AdbCapture()
    if target_kind == target_module.KIND_DESKTOP:
        from auto_control_script.capture.desktop_capture import DesktopCapture

        return DesktopCapture()
    raise target_module.TargetUnavailableError(
        f"capture.factory.create_capture: 目标类型非法 (kind={target_kind!r})，"
        f"可选值为 {[target_module.KIND_WINDOW, target_module.KIND_DEVICE, target_module.KIND_DESKTOP]}"
    )


def capture(target: Target, path: Optional[str] = None) -> Frame:
    """
    截取目标画面，Windows 窗口与安卓设备统一入口。

    Args:
        target (Target): 目标对象
        path (str): 取图路径，None 时取配置中的 capture_path

    Returns:
        Frame: 画面帧，坐标原点为客户区（窗口）或屏幕（设备）左上角

    Raises:
        ChannelUnavailableError: 取图路径对该目标类型不适用时抛出
    """
    return create_capture(target.kind).capture(target, path or SETTINGS["capture_path"])


def capture_region(target: Target, region: tuple, path: Optional[str] = None) -> Frame:
    """
    截取目标的指定区域。

    Args:
        target (Target): 目标对象
        region (tuple): (x1, y1, x2, y2) 区域坐标
        path (str): 取图路径，None 时取配置默认值

    Returns:
        Frame: 区域画面帧
    """
    return crop_frame(capture(target, path), region)


def save(target: Target, filepath: str, region: Optional[tuple] = None, path: Optional[str] = None) -> Frame:
    """
    截取目标画面并保存为图片文件。

    Args:
        target (Target): 目标对象
        filepath (str): 保存路径
        region (tuple): 为 None 时保存整幅画面，否则保存该区域
        path (str): 取图路径，None 时取配置默认值

    Returns:
        Frame: 实际保存的画面帧
    """
    result = capture_region(target, region, path) if region else capture(target, path)
    save_frame(result, filepath)
    logger.info(f"capture.factory.save: 已保存画面到 {filepath}（{result.width}x{result.height}）")
    return result


def release(target: Optional[Target] = None) -> None:
    """
    释放取图资源。

    Args:
        target (Target): 目标对象，None 时释放全部目标的取图会话
    """
    if target is None:
        from auto_control_script.capture.window_capture import release as release_windows

        release_windows()
        return
    create_capture(target.kind).release(target)
