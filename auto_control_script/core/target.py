# -*- coding: utf-8 -*-
"""
target.py - 自动化目标抽象模块

职责:
- 用统一的 Target 抽象描述 Windows 窗口与安卓设备
- 枚举本机可用目标、按标识或名称解析目标、刷新目标状态

调用链:
- cli.py / web/app.py / runner.py -> target.py -> window_manager.py / adb.py

坐标约定:
- Target.width / height 是图像像素尺寸，即本项目的对外统一坐标空间，
  与 Frame 的像素坐标一一对应
"""

from dataclasses import dataclass, field

import win32gui

from auto_control_script.core import window_manager
from auto_control_script.utils import adb
from auto_control_script.core.errors import TargetUnavailableError

KIND_WINDOW = "window"
"""str: 目标类型——Windows 窗口。"""

KIND_DEVICE = "device"
"""str: 目标类型——安卓设备。"""

KIND_DESKTOP = "desktop"
"""str: 目标类型——整个屏幕（虚拟屏幕，含所有显示器）。"""

KIND_ALL = "all"
"""str: 枚举时的"全部类型"取值。"""


@dataclass
class Target:
    """
    一个自动化目标，代表一个 Windows 窗口或一台安卓设备。

    Attributes:
        kind (str): 目标类型，取 KIND_WINDOW 或 KIND_DEVICE
        id (str): 稳定标识，窗口为句柄数值串，设备为 adb serial
        name (str): 人类可读名称，窗口为标题，设备为型号或 serial
        width (int): 图像像素宽度，即对外坐标空间的宽度
        height (int): 图像像素高度
        available (bool): 目标当前是否可用
        visible (bool): 目标当前是否可见；窗口取 Win32 的 IsWindowVisible 结果，
            设备固定为 True（设备无可见性概念）
        meta (dict): 差异信息，窗口含 class_name、client_width、client_height；
            设备含 state、product、连接方式
    """

    kind: str
    id: str
    name: str
    width: int = 0
    height: int = 0
    available: bool = False
    visible: bool = True
    meta: dict = field(default_factory=dict)


def build_window_target(hwnd: int) -> Target:
    """
    按窗口句柄构造窗口目标，并测量其几何信息。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        Target: 窗口目标

    Raises:
        TargetUnavailableError: 句柄无效时抛出
    """
    manager = window_manager.WindowManager(hwnd)
    return Target(
        kind=KIND_WINDOW,
        id=str(hwnd),
        name=manager.title,
        width=manager.pixel_width,
        height=manager.pixel_height,
        available=True,
        visible=bool(win32gui.IsWindowVisible(hwnd)),
        meta={
            "class_name": win_class_name(hwnd),
            "client_width": manager.client_width,
            "client_height": manager.client_height,
        },
    )


def win_class_name(hwnd: int) -> str:
    """
    获取窗口类名。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        str: 窗口类名，句柄无效时返回空字符串
    """
    return win32gui.GetClassName(hwnd)


def build_device_target(serial: str, state: str = "device", product: str = "") -> Target:
    """
    按设备序列号构造设备目标，并查询其分辨率。

    Args:
        serial (str): 设备序列号
        state (str): adb 报告的设备状态
        product (str): 设备型号，为空时以 serial 作为名称

    Returns:
        Target: 设备目标

    Raises:
        TargetUnavailableError: 设备离线或分辨率查询失败时抛出
    """
    online = state == "device"
    if not online:
        return Target(
            kind=KIND_DEVICE,
            id=serial,
            name=product or serial,
            available=False,
            meta={"state": state, "product": product, "connection": _connection_kind(serial)},
        )
    width, height = device_size(serial)
    return Target(
        kind=KIND_DEVICE,
        id=serial,
        name=product or serial,
        width=width,
        height=height,
        available=True,
        meta={"state": state, "product": product, "connection": _connection_kind(serial)},
    )


def _connection_kind(serial: str) -> str:
    """
    判断设备的连接方式。

    Args:
        serial (str): 设备序列号

    Returns:
        str: 含冒号判为 "tcp"，否则为 "usb"
    """
    return "tcp" if ":" in serial else "usb"


def device_size(serial: str) -> tuple:
    """
    查询设备的物理分辨率。

    Args:
        serial (str): 设备序列号

    Returns:
        tuple: (width, height) 物理分辨率

    Raises:
        TargetUnavailableError: 输出中没有 Physical size 时抛出
    """
    output = adb.run(["shell", "wm", "size"], serial=serial)
    for line in output.splitlines():
        if "Physical size:" in line:
            size_text = line.split(":", 1)[1].strip()
            width_text, height_text = size_text.split("x")
            return int(width_text), int(height_text)
    raise TargetUnavailableError(
        f"target.device_size: 未能从 adb 输出中解析设备 {serial} 的分辨率，"
        f"adb shell wm size 输出={output!r}"
    )


def build_desktop_target() -> Target:
    """
    构造整屏目标（虚拟屏幕，覆盖所有显示器）。

    Returns:
        Target: 整屏目标，标识与类型均为 desktop
    """
    from auto_control_script.capture.desktop_capture import virtual_screen

    left, top, width, height = virtual_screen()
    return Target(
        kind=KIND_DESKTOP,
        id=KIND_DESKTOP,
        name="整个屏幕",
        width=width,
        height=height,
        available=width > 0 and height > 0,
        visible=True,
        meta={"left": left, "top": top},
    )


def list_targets(kind: str = KIND_ALL) -> list:
    """
    枚举可用目标。

    Args:
        kind (str): KIND_WINDOW / KIND_DEVICE / KIND_DESKTOP / KIND_ALL

    Returns:
        list: Target 列表；窗口在前、设备在后，均按名称排序

    Raises:
        ValueError: kind 取值非法时抛出
    """
    if kind not in (KIND_WINDOW, KIND_DEVICE, KIND_DESKTOP, KIND_ALL):
        raise ValueError(
            f"target.list_targets: kind 取值非法 (实际={kind!r})，"
            f"可选值为 {[KIND_WINDOW, KIND_DEVICE, KIND_DESKTOP, KIND_ALL]}"
        )
    targets = []
    if kind in (KIND_DESKTOP, KIND_ALL):
        targets.append(build_desktop_target())
    if kind in (KIND_WINDOW, KIND_ALL):
        for item in window_manager.list_windows():
            hwnd = item["hwnd"]
            if win32gui.IsIconic(hwnd):
                continue
            width, height = window_manager.client_size(hwnd)
            if width <= 0 or height <= 0:
                continue
            targets.append(build_window_target(hwnd))
    if kind in (KIND_DEVICE, KIND_ALL):
        for device in adb.list_devices():
            targets.append(build_device_target(
                serial=device["serial"],
                state=device["state"],
                product=device["product"],
            ))
    targets.sort(key=lambda item: (item.kind != KIND_WINDOW, item.name))
    return targets


def resolve_target(selector: str) -> Target:
    """
    按标识或名称解析出唯一目标。

    解析顺序：窗口句柄（纯数字）-> 窗口标题精确匹配 -> 窗口标题子串匹配
    -> 设备序列号精确匹配。子串匹配到多个窗口时报错要求使用者给出更精确的条件。

    Args:
        selector (str): 窗口句柄、窗口标题或设备序列号

    Returns:
        Target: 解析出的目标

    Raises:
        TargetUnavailableError: 找不到目标或匹配不唯一时抛出
    """
    selector = selector.strip()
    if selector.lower() in (KIND_DESKTOP, "整个屏幕"):
        return build_desktop_target()
    if selector.isdigit():
        hwnd = int(selector)
        if window_manager.is_window(hwnd):
            return build_window_target(hwnd)
        raise TargetUnavailableError(
            f"target.resolve_target: 句柄 {hwnd} 不是有效窗口（可能已关闭）"
        )

    for item in window_manager.list_windows():
        if item["title"] == selector:
            return build_window_target(item["hwnd"])

    fuzzy = [item for item in window_manager.list_windows() if selector in item["title"]]
    if len(fuzzy) == 1:
        return build_window_target(fuzzy[0]["hwnd"])
    if len(fuzzy) > 1:
        raise TargetUnavailableError(
            f"target.resolve_target: 标题包含 {selector!r} 的窗口有 {len(fuzzy)} 个，"
            f"无法唯一确定目标；命中列表={[(item['hwnd'], item['title']) for item in fuzzy]}；"
            f"请改用完整标题或窗口句柄"
        )

    devices = adb.list_devices()
    for device in devices:
        if device["serial"] == selector:
            return build_device_target(
                serial=device["serial"],
                state=device["state"],
                product=device["product"],
            )
    raise TargetUnavailableError(
        f"target.resolve_target: 未找到匹配 {selector!r} 的窗口或设备；"
        f"可用设备={[device['serial'] for device in devices]}；"
        f"可用窗口={[item['title'] for item in window_manager.list_windows()]}"
    )


def _current_device_info(serial: str, fallback_product: str) -> tuple:
    """
    查询设备当前的 adb 状态与型号。

    Args:
        serial (str): 设备序列号
        fallback_product (str): 设备已不在 adb 列表中时沿用的型号

    Returns:
        tuple: (str 状态, str 型号)；设备不在 adb 列表中时状态为 "offline"
    """
    for device in adb.list_devices():
        if device["serial"] == serial:
            return device["state"], device["product"] or fallback_product
    return "offline", fallback_product


def refresh(target: Target) -> Target:
    """
    刷新目标的尺寸与可用状态，就地更新后返回。

    设备目标每次刷新都重新查询 `adb devices`，使设备离线与上线能被自动感知，
    不沿用目标缓存的状态。

    Args:
        target (Target): 待刷新的目标

    Returns:
        Target: 刷新后的同一目标对象

    Raises:
        TargetUnavailableError: 目标已失效时抛出
    """
    if target.kind == KIND_WINDOW:
        if not window_manager.is_window(int(target.id)):
            target.available = False
            raise TargetUnavailableError(
                f"target.refresh: 窗口 {target.id}（{target.name!r}）已失效"
            )
        updated = build_window_target(int(target.id))
    elif target.kind == KIND_DEVICE:
        state, product = _current_device_info(target.id, target.meta.get("product", ""))
        updated = build_device_target(serial=target.id, state=state, product=product)
    else:
        raise TargetUnavailableError(
            f"target.refresh: 目标类型非法 (kind={target.kind!r})，"
            f"可选值为 {[KIND_WINDOW, KIND_DEVICE]}"
        )
    target.width = updated.width
    target.height = updated.height
    target.available = updated.available
    target.meta = updated.meta
    return target


def require_available(target: Target, action: str) -> None:
    """
    校验目标可用，不可用即报错。

    Args:
        target (Target): 待校验的目标
        action (str): 将要执行的动作描述，用于拼进错误信息

    Raises:
        TargetUnavailableError: 目标不可用时抛出
    """
    if not target.available:
        raise TargetUnavailableError(
            f"target.require_available: 目标 {target.id}（{target.name!r}，kind={target.kind}）"
            f"当前不可用，无法执行 {action}"
        )
