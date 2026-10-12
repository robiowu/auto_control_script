# -*- coding: utf-8 -*-
"""
interaction/win_background.py - Windows 后台输入模块

职责:
- 通过窗口消息投递完成输入，不激活目标、不改变前台焦点与鼠标位置

调用链:
- interaction/factory.py -> interaction/win_background.py
    -> interaction/key_codes.py / core/window_manager.py

限制（原样暴露，不假装成功）:
- 后台消息投递无法验证动作是否真的被目标应用处理，PostMessage 成功仅代表消息入队；
  结果校验交给脚本中的"截图比对"步骤完成
"""

import time

import win32api
import win32gui

from auto_control_script.core.errors import ActionError
from auto_control_script.core.settings import SETTINGS
from auto_control_script.core.target import KIND_WINDOW
from auto_control_script.core.window_manager import WindowManager
from auto_control_script.interaction.base import (
    MODE_BACKGROUND, ACTION_CLICK, ACTION_DOUBLE_CLICK, ACTION_DRAG, ACTION_HOTKEY,
    ACTION_INPUT_TEXT, ACTION_KEY, ACTION_LONG_PRESS, ACTION_MOVE, ACTION_RIGHT_CLICK,
    ACTION_SCROLL, LONG_PRESS_MS,
    Action, BaseInteraction,
)
from auto_control_script.interaction.key_codes import get_vk_code

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0206
WM_MBUTTONUP = 0x0207
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

WHEEL_DELTA = 120
"""int: 一格滚轮对应的增量值。"""

DRAG_STEPS = 10
"""int: 拖拽过程中间移动的步数。"""


def _key_lparam(vk_code: int, is_up: bool) -> int:
    """
    构造键盘消息的 lparam。

    Args:
        vk_code (int): 虚拟键码
        is_up (bool): 是否为按键抬起消息

    Returns:
        int: 键盘消息 lparam
    """
    scan_code = win32api.MapVirtualKey(vk_code, 0)
    lparam = 1 | (scan_code << 16)
    if is_up:
        lparam |= (1 << 30) | (1 << 31)
    return lparam


def _post(hwnd: int, message: int, wparam: int, lparam: int) -> None:
    """
    向窗口投递消息并检查投递结果。

    Args:
        hwnd (int): 窗口句柄
        message (int): 消息类型
        wparam (int): 消息 wparam
        lparam (int): 消息 lparam

    Raises:
        ActionError: 消息投递失败（窗口失效或消息队列不可用）时抛出
    """
    ok = win32gui.PostMessage(hwnd, message, wparam, lparam)
    if not ok:
        raise ActionError(
            f"interaction.win_background._post: 向窗口 {hwnd} 投递消息 0x{message:04X} 失败；"
            f"窗口可能已失效或其消息队列不可用"
        )


def _click(manager: WindowManager, x: int, y: int, button: str) -> None:
    """
    后台点击。

    Args:
        manager (WindowManager): 窗口几何管理器
        x (int): 图像横坐标
        y (int): 图像纵坐标
        button (str): left / right / middle
    """
    message_x, message_y = manager.to_message(x, y)
    lparam = win32api.MAKELONG(message_x, message_y)
    if button == "left":
        down, up = WM_LBUTTONDOWN, WM_LBUTTONUP
    elif button == "right":
        down, up = WM_RBUTTONDOWN, WM_RBUTTONUP
    else:
        down, up = WM_MBUTTONDOWN, WM_MBUTTONUP
    _post(manager.hwnd, WM_MOUSEMOVE, 0, lparam)
    _post(manager.hwnd, down, 1, lparam)
    time.sleep(SETTINGS["click_delay"])
    _post(manager.hwnd, up, 0, lparam)


def _long_press(manager: WindowManager, x: int, y: int, duration_ms: int) -> None:
    """
    后台长按：按下左键后保持指定时长再抬起。

    Args:
        manager (WindowManager): 窗口几何管理器
        x (int): 图像横坐标
        y (int): 图像纵坐标
        duration_ms (int): 按住时长毫秒数
    """
    message_x, message_y = manager.to_message(x, y)
    lparam = win32api.MAKELONG(message_x, message_y)
    _post(manager.hwnd, WM_MOUSEMOVE, 0, lparam)
    _post(manager.hwnd, WM_LBUTTONDOWN, 1, lparam)
    time.sleep(duration_ms / 1000)
    _post(manager.hwnd, WM_LBUTTONUP, 0, lparam)


class WinBackgroundInteraction(BaseInteraction):
    """
    Windows 后台输入执行器。

    Attributes:
        kind (str): 固定为 KIND_WINDOW
        mode (str): 固定为 MODE_BACKGROUND
    """

    kind = KIND_WINDOW
    mode = MODE_BACKGROUND

    def execute(self, target, action: Action) -> None:
        """
        以后台方式执行一次输入动作。

        Args:
            target (Target): 窗口目标
            action (Action): 动作规格

        Raises:
            ActionError: 动作不被后台方式支持时抛出
        """
        manager = WindowManager(int(target.id))
        manager.refresh()
        hwnd = manager.hwnd

        if action.kind == ACTION_CLICK:
            _click(manager, action.point[0], action.point[1], "left")
        elif action.kind == ACTION_RIGHT_CLICK:
            _click(manager, action.point[0], action.point[1], "right")
        elif action.kind == ACTION_DOUBLE_CLICK:
            _click(manager, action.point[0], action.point[1], "left")
            _click(manager, action.point[0], action.point[1], "left")
        elif action.kind == ACTION_LONG_PRESS:
            duration = int(action.text) if action.text else LONG_PRESS_MS
            _long_press(manager, action.point[0], action.point[1], duration)
        elif action.kind == ACTION_MOVE:
            message_x, message_y = manager.to_message(action.point[0], action.point[1])
            _post(hwnd, WM_MOUSEMOVE, 0, win32api.MAKELONG(message_x, message_y))
        elif action.kind == ACTION_DRAG:
            self._drag(manager, action)
        elif action.kind == ACTION_SCROLL:
            self._scroll(manager, action)
        elif action.kind == ACTION_KEY:
            self._key(hwnd, action.text)
        elif action.kind == ACTION_HOTKEY:
            self._hotkey(hwnd, action.text)
        elif action.kind == ACTION_INPUT_TEXT:
            self._input_text(hwnd, action.text)
        else:
            raise ActionError(
                f"interaction.win_background.WinBackgroundInteraction.execute: "
                f"后台方式不支持动作 {action.kind!r}"
            )

    def _drag(self, manager: WindowManager, action: Action) -> None:
        """
        后台拖拽，中途插值移动以保证目标能收到连续的移动消息。

        Args:
            manager (WindowManager): 窗口几何管理器
            action (Action): 动作规格，point 为起点、end_point 为终点
        """
        hwnd = manager.hwnd
        start_x, start_y = manager.to_message(action.point[0], action.point[1])
        end_x, end_y = manager.to_message(action.end_point[0], action.end_point[1])
        _post(hwnd, WM_MOUSEMOVE, 0, win32api.MAKELONG(start_x, start_y))
        _post(hwnd, WM_LBUTTONDOWN, 1, win32api.MAKELONG(start_x, start_y))
        for step in range(1, DRAG_STEPS + 1):
            current_x = start_x + (end_x - start_x) * step // DRAG_STEPS
            current_y = start_y + (end_y - start_y) * step // DRAG_STEPS
            _post(hwnd, WM_MOUSEMOVE, 1, win32api.MAKELONG(current_x, current_y))
            time.sleep(0.01)
        _post(hwnd, WM_LBUTTONUP, 0, win32api.MAKELONG(end_x, end_y))

    def _scroll(self, manager: WindowManager, action: Action) -> None:
        """
        后台滚动滚轮。

        Args:
            manager (WindowManager): 窗口几何管理器
            action (Action): 动作规格，text 为滚动量，正数向上、负数向下
        """
        message_x, message_y = manager.to_message(action.point[0], action.point[1])
        amount = int(action.text)
        _post(manager.hwnd, WM_MOUSEWHEEL, (amount * WHEEL_DELTA) << 16,
              win32api.MAKELONG(message_x, message_y))

    def _key(self, hwnd: int, key: str) -> None:
        """
        后台按下一个按键。

        Args:
            hwnd (int): 窗口句柄
            key (str): 按键名或单字符
        """
        vk_code = get_vk_code(key)
        _post(hwnd, WM_KEYDOWN, vk_code, _key_lparam(vk_code, False))
        time.sleep(SETTINGS["click_delay"])
        _post(hwnd, WM_KEYUP, vk_code, _key_lparam(vk_code, True))

    def _hotkey(self, hwnd: int, hotkey: str) -> None:
        """
        后台按下组合键，如 "ctrl+c"。

        Args:
            hwnd (int): 窗口句柄
            hotkey (str): 组合键，"+" 连接
        """
        parts = [item.strip().lower() for item in hotkey.split("+")]
        codes = [get_vk_code(item) for item in parts]
        for code in codes:
            _post(hwnd, WM_KEYDOWN, code, _key_lparam(code, False))
        for code in reversed(codes):
            _post(hwnd, WM_KEYUP, code, _key_lparam(code, True))

    def _input_text(self, hwnd: int, text: str) -> None:
        """
        后台逐字符输入文本，支持中文。

        Args:
            hwnd (int): 窗口句柄
            text (str): 待输入文本
        """
        for char in text:
            _post(hwnd, WM_CHAR, ord(char), 1)
            time.sleep(SETTINGS["type_delay"])
