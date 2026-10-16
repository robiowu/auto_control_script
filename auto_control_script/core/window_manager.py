# -*- coding: utf-8 -*-
"""
window_manager.py - Windows 窗口管理模块

职责:
- 枚举本机可见窗口、按标题或类名查找窗口句柄
- 提供窗口几何信息：客户区逻辑尺寸、图像像素尺寸、边框偏移、缩放比
- 提供坐标换算：图像坐标 -> 屏幕坐标（前台输入）、图像坐标 -> 消息坐标（后台输入）
- 提供窗口置顶

调用链:
- target.py -> window_manager.py -> win32gui / ctypes(user32)
- capture_win.py -> window_manager.py
- input_win.py -> window_manager.py

说明:
- 本模块由 win_handle.py 重构而来，只保留与"定位 + 几何 + 坐标"相关的能力，
  窗口点击等输入能力已迁入 input_win.py
"""

import ctypes
import ctypes.wintypes

import pywintypes
import win32con
import win32gui

from typing import Optional
from auto_control_script.core.errors import CaptureError, TargetUnavailableError

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
"""int: 每显示器 DPI 感知 v2 的上下文常量，用于让本进程拿到物理屏幕坐标。"""

_user32 = ctypes.windll.user32
_user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_ssize_t]
_user32.SetProcessDpiAwarenessContext.restype = ctypes.c_int
_user32.GetThreadDpiAwarenessContext.restype = ctypes.c_ssize_t
_user32.AreDpiAwarenessContextsEqual.argtypes = [ctypes.c_ssize_t, ctypes.c_ssize_t]
_user32.AreDpiAwarenessContextsEqual.restype = ctypes.c_int


def ensure_dpi_awareness() -> None:
    """
    将本进程设置为每显示器 DPI 感知 v2。

    设置后 GetWindowRect / ClientToScreen 返回的才是物理屏幕坐标，
    这是"图像坐标 == 点击坐标"成立的前提。已处于该感知级别时不重复设置。

    Raises:
        RuntimeError: 设置失败时抛出，消息含系统返回的最后一个错误码
    """
    current = _user32.GetThreadDpiAwarenessContext()
    already_aware = _user32.AreDpiAwarenessContextsEqual(
        current, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    )
    if already_aware:
        return
    ok = _user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    if not ok:
        raise RuntimeError(
            f"window_manager.ensure_dpi_awareness: 设置进程 DPI 感知失败，"
            f"GetLastError={ctypes.get_last_error()}；本平台要求 Windows 10 1703 及以上"
        )


def is_window(hwnd: int) -> bool:
    """
    判断句柄是否指向一个有效窗口。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        bool: 有效返回 True，否则 False
    """
    return bool(win32gui.IsWindow(hwnd))


def window_title(hwnd: int) -> str:
    """
    获取窗口标题。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        str: 窗口标题，句柄无效时返回空字符串
    """
    return win32gui.GetWindowText(hwnd)


def client_size(hwnd: int) -> tuple:
    """
    获取窗口客户区的逻辑尺寸，不做任何校验。

    用于在枚举窗口时过滤掉不可作为自动化目标的窗口（隐藏窗口、零尺寸窗口）。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        tuple: (width, height)，窗口无效或尺寸为 0 时返回 (0, 0)
    """
    if not is_window(hwnd):
        return 0, 0
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    return right - left, bottom - top


def list_windows(visible_only: bool = True) -> list:
    """
    枚举本机窗口。

    Args:
        visible_only (bool): 是否只返回可见窗口，默认 True

    Returns:
        list: 窗口信息列表，每项为 dict，含 hwnd、title、class_name 三个键
    """
    ensure_dpi_awareness()
    windows = []

    def _collect(hwnd: int, _param) -> bool:
        if visible_only and not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return True
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "class_name": win32gui.GetClassName(hwnd),
        })
        return True

    win32gui.EnumWindows(_collect, None)
    return windows


def find_window(title: Optional[str] = None, class_name: Optional[str] = None, exact: bool = True) -> int:
    """
    按标题和/或类名查找窗口句柄。

    Args:
        title (str): 窗口标题，None 表示不限标题
        class_name (str): 窗口类名，None 表示不限类名
        exact (bool): True 时标题完全匹配，False 时子串匹配

    Returns:
        int: 命中的窗口句柄

    Raises:
        TargetUnavailableError: 未找到窗口，或子串匹配到多个窗口时抛出
    """
    if title is None and class_name is None:
        raise TargetUnavailableError(
            "window_manager.find_window: title 与 class_name 不能同时为 None"
        )
    matched = []
    for item in list_windows():
        if class_name is not None and item["class_name"] != class_name:
            continue
        if title is not None:
            hit = item["title"] == title if exact else title in item["title"]
            if not hit:
                continue
        matched.append(item)
    if not matched:
        raise TargetUnavailableError(
            f"window_manager.find_window: 未找到窗口，条件为 title={title!r}、"
            f"class_name={class_name!r}、exact={exact}"
        )
    if len(matched) > 1:
        raise TargetUnavailableError(
            f"window_manager.find_window: 条件匹配到 {len(matched)} 个窗口，无法唯一确定目标；"
            f"命中列表={[(item['hwnd'], item['title']) for item in matched]}；"
            f"请改用更精确的标题或直接使用窗口句柄"
        )
    return matched[0]["hwnd"]


class WindowManager:
    """
    单个窗口的几何管理器。

    每次 refresh() 都会重新测量窗口矩形、客户区矩形与缩放比，
    因此窗口被移动、缩放或跨屏后坐标依然正确。

    Attributes:
        hwnd (int): 窗口句柄
        client_width (int): 客户区逻辑宽度（窗口消息坐标空间）
        client_height (int): 客户区逻辑高度
        pixel_width (int): 客户区图像像素宽度（本项目的对外坐标空间）
        pixel_height (int): 客户区图像像素高度
        offset_x (int): 客户区左上角相对窗口矩形左上角的横向偏移（含边框）
        offset_y (int): 客户区左上角相对窗口矩形左上角的纵向偏移（含标题栏）
        origin_x (int): 客户区左上角的屏幕横坐标
        origin_y (int): 客户区左上角的屏幕纵坐标
        window_width (int): 窗口整体宽度（含边框与标题栏）
        window_height (int): 窗口整体高度
    """

    def __init__(self, hwnd: int):
        """
        初始化窗口管理器并立即测量几何信息。

        Args:
            hwnd (int): 窗口句柄

        Raises:
            TargetUnavailableError: 句柄无效时抛出
        """
        if not is_window(hwnd):
            raise TargetUnavailableError(
                f"WindowManager.__init__: 窗口句柄 {hwnd} 无效（窗口可能已关闭）"
            )
        self.hwnd = hwnd
        self.client_width = 0
        self.client_height = 0
        self.pixel_width = 0
        self.pixel_height = 0
        self.offset_x = 0
        self.offset_y = 0
        self.origin_x = 0
        self.origin_y = 0
        self.window_width = 0
        self.window_height = 0
        self.refresh()

    @property
    def title(self) -> str:
        """str: 当前窗口标题。"""
        return window_title(self.hwnd)

    def refresh(self) -> None:
        """
        重新测量窗口几何信息。

        Raises:
            TargetUnavailableError: 窗口已关闭时抛出
            CaptureError: 窗口处于最小化状态或客户区尺寸为 0 时抛出
        """
        ensure_dpi_awareness()
        if not is_window(self.hwnd):
            raise TargetUnavailableError(
                f"WindowManager.refresh: 窗口 {self.hwnd} 已失效（可能已关闭）"
            )
        if win32gui.IsIconic(self.hwnd):
            raise CaptureError(
                f"WindowManager.refresh: 窗口 {self.hwnd}（{self.title!r}）处于最小化状态，"
                f"无法测量客户区也无法截图，请先恢复窗口"
            )
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        self.window_width = right - left
        self.window_height = bottom - top

        client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(self.hwnd)
        self.client_width = client_right - client_left
        self.client_height = client_bottom - client_top
        if self.client_width <= 0 or self.client_height <= 0:
            raise CaptureError(
                f"WindowManager.refresh: 窗口 {self.hwnd}（{self.title!r}）的客户区尺寸为 "
                f"{self.client_width}x{self.client_height}，无法截图"
            )

        origin_x, origin_y = win32gui.ClientToScreen(self.hwnd, (0, 0))
        end_x, end_y = win32gui.ClientToScreen(self.hwnd, (self.client_width, self.client_height))
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.pixel_width = end_x - origin_x
        self.pixel_height = end_y - origin_y
        self.offset_x = origin_x - left
        self.offset_y = origin_y - top
        if self.pixel_width <= 0 or self.pixel_height <= 0:
            raise CaptureError(
                f"WindowManager.refresh: 窗口 {self.hwnd}（{self.title!r}）的客户区像素尺寸为 "
                f"{self.pixel_width}x{self.pixel_height}，无法截图"
            )

    @property
    def scale_x(self) -> float:
        """float: 横向缩放比（图像像素 / 客户区逻辑像素）。"""
        return self.pixel_width / self.client_width

    @property
    def scale_y(self) -> float:
        """float: 纵向缩放比（图像像素 / 客户区逻辑像素）。"""
        return self.pixel_height / self.client_height

    def to_screen(self, x: float, y: float) -> tuple:
        """
        把图像坐标换算为物理屏幕坐标，供前台输入使用。

        Args:
            x (float): 图像横坐标
            y (float): 图像纵坐标

        Returns:
            tuple: (screen_x, screen_y) 物理屏幕坐标
        """
        return int(self.origin_x + x), int(self.origin_y + y)

    def to_message(self, x: float, y: float) -> tuple:
        """
        把图像坐标换算为窗口消息坐标，供后台输入使用。

        Args:
            x (float): 图像横坐标
            y (float): 图像纵坐标

        Returns:
            tuple: (message_x, message_y) 窗口消息坐标（客户区逻辑像素）
        """
        return int(round(x / self.scale_x)), int(round(y / self.scale_y))

    def to_image(self, message_x: float, message_y: float) -> tuple:
        """
        把窗口消息坐标换算为图像坐标。

        Args:
            message_x (float): 窗口消息横坐标
            message_y (float): 窗口消息纵坐标

        Returns:
            tuple: (x, y) 图像坐标
        """
        return int(round(message_x * self.scale_x)), int(round(message_y * self.scale_y))

    def bring_to_front(self) -> None:
        """
        把窗口激活到前台。仅在前台输入方式下调用。

        Raises:
            TargetUnavailableError: 窗口已失效或激活失败时抛出
        """
        if not is_window(self.hwnd):
            raise TargetUnavailableError(
                f"WindowManager.bring_to_front: 窗口 {self.hwnd} 已失效，无法激活"
            )
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except pywintypes.error as error:
            # 系统拒绝非前台进程抢占焦点时，该调用直接抛异常而非返回失败；
            # 不捕获会穿透到命令行顶层，导致退出码失控（非约定的 4）
            raise TargetUnavailableError(
                f"WindowManager.bring_to_front: 窗口 {self.hwnd}（{self.title!r}）激活失败，"
                f"系统拒绝抢占前台焦点；可稍后重试或手动点击该窗口，底层错误={error}"
            ) from error
        if win32gui.GetForegroundWindow() != self.hwnd:
            raise TargetUnavailableError(
                f"WindowManager.bring_to_front: 窗口 {self.hwnd}（{self.title!r}）激活失败，"
                f"系统不允许抢占前台焦点；可稍后重试或手动点击该窗口"
            )
