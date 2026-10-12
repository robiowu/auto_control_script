# -*- coding: utf-8 -*-
"""
interaction/win_foreground.py - Windows 前台输入模块

职责:
- 通过真实鼠标键盘完成输入，对全屏与游戏窗口兼容性更好
- 执行前会激活目标窗口并提示使用者

调用链:
- interaction/factory.py -> interaction/win_foreground.py
    -> core/window_manager.py / pydirectinput / pyperclip

注意:
- 本方式会改变前台焦点与真实鼠标位置，执行期间使用者不应操作键鼠
"""

import time

import pydirectinput
import pyperclip
import win32api

from auto_control_script.core.errors import ActionError
from auto_control_script.core.settings import SETTINGS
from auto_control_script.core.target import KIND_WINDOW
from auto_control_script.core.window_manager import WindowManager
from auto_control_script.interaction.base import (
    MODE_FOREGROUND, ACTION_CLICK, ACTION_DOUBLE_CLICK, ACTION_DRAG, ACTION_HOTKEY,
    ACTION_INPUT_TEXT, ACTION_KEY, ACTION_MOVE, ACTION_RIGHT_CLICK, ACTION_SCROLL,
    Action, BaseInteraction,
)

pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0

MOUSEEVENTF_WHEEL = 0x0800
"""int: mouse_event 的滚轮事件标志。"""

WHEEL_DELTA = 120
"""int: 一格滚轮对应的增量值。"""

DRAG_DURATION = 0.2
"""float: 前台拖拽的移动耗时秒数。"""


class WinForegroundInteraction(BaseInteraction):
    """
    Windows 前台输入执行器。

    Attributes:
        kind (str): 固定为 KIND_WINDOW
        mode (str): 固定为 MODE_FOREGROUND
    """

    kind = KIND_WINDOW
    mode = MODE_FOREGROUND

    def execute(self, target, action: Action) -> None:
        """
        以前台方式执行一次输入动作（会激活目标窗口）。

        Args:
            target (Target): 窗口目标
            action (Action): 动作规格

        Raises:
            ActionError: 动作不被前台方式支持时抛出
        """
        manager = WindowManager(int(target.id))
        manager.refresh()
        manager.bring_to_front()

        if action.kind in (ACTION_CLICK, ACTION_RIGHT_CLICK, ACTION_DOUBLE_CLICK,
                           ACTION_MOVE, ACTION_DRAG, ACTION_SCROLL):
            screen_x, screen_y = manager.to_screen(action.point[0], action.point[1])

        if action.kind == ACTION_CLICK:
            pydirectinput.click(screen_x, screen_y)
        elif action.kind == ACTION_RIGHT_CLICK:
            pydirectinput.rightClick(screen_x, screen_y)
        elif action.kind == ACTION_DOUBLE_CLICK:
            pydirectinput.doubleClick(screen_x, screen_y)
        elif action.kind == ACTION_MOVE:
            pydirectinput.moveTo(screen_x, screen_y)
        elif action.kind == ACTION_DRAG:
            self._drag(manager, action)
        elif action.kind == ACTION_SCROLL:
            self._scroll(screen_x, screen_y, action)
        elif action.kind == ACTION_KEY:
            pydirectinput.press(action.text.strip().lower())
        elif action.kind == ACTION_HOTKEY:
            self._hotkey(action.text)
        elif action.kind == ACTION_INPUT_TEXT:
            self._input_text(action.text)
        else:
            raise ActionError(
                f"interaction.win_foreground.WinForegroundInteraction.execute: "
                f"前台方式不支持动作 {action.kind!r}"
            )

    def _drag(self, manager: WindowManager, action: Action) -> None:
        """
        前台拖拽。

        Args:
            manager (WindowManager): 窗口几何管理器
            action (Action): 动作规格，point 为起点、end_point 为终点
        """
        end_x, end_y = manager.to_screen(action.end_point[0], action.end_point[1])
        start_x, start_y = manager.to_screen(action.point[0], action.point[1])
        pydirectinput.mouseDown(start_x, start_y)
        pydirectinput.moveTo(end_x, end_y, duration=DRAG_DURATION)
        pydirectinput.mouseUp(end_x, end_y)

    def _scroll(self, screen_x: int, screen_y: int, action: Action) -> None:
        """
        前台滚动滚轮。

        Args:
            screen_x (int): 屏幕横坐标
            screen_y (int): 屏幕纵坐标
            action (Action): 动作规格，text 为滚动量，正数向上、负数向下
        """
        amount = int(action.text)
        win32api.mouse_event(MOUSEEVENTF_WHEEL, screen_x, screen_y, amount * WHEEL_DELTA, 0)

    def _hotkey(self, hotkey: str) -> None:
        """
        前台按下组合键，如 "ctrl+v"。

        Args:
            hotkey (str): 组合键，"+" 连接
        """
        parts = [item.strip().lower() for item in hotkey.split("+")]
        pydirectinput.hotkey(*parts)

    def _input_text(self, text: str) -> None:
        """
        前台输入文本，经剪贴板粘贴以支持中文。

        Args:
            text (str): 待输入文本
        """
        pyperclip.copy(text)
        pydirectinput.hotkey("ctrl", "v")
        time.sleep(SETTINGS["type_delay"])
