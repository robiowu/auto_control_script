# -*- coding: utf-8 -*-
"""
input_adb.py - 安卓设备输入模块

职责:
- 通过 adb shell input 下发点击、双击、拖拽、滑动、按键与文本输入

调用链:
- interaction.py -> input_adb.py -> adb.py

限制（原样暴露，不做静默兜底）:
- 触摸设备没有悬停与右键概念，move 与 right_click 直接报错
- adb shell input 不支持组合键，hotkey 直接报错
- adb shell input text 只支持 ASCII，含中文等非 ASCII 文本时直接报错并给出说明
"""

from auto_control_script.core.errors import ActionError
from auto_control_script.core.target import KIND_DEVICE
from auto_control_script.interaction.base import (
    MODE_BACKGROUND, ACTION_CLICK, ACTION_DOUBLE_CLICK, ACTION_DRAG, ACTION_HOTKEY,
    ACTION_INPUT_TEXT, ACTION_KEY, ACTION_KINDS, ACTION_MOVE, ACTION_RIGHT_CLICK,
    ACTION_SCROLL, Action, BaseInteraction,
)
from auto_control_script.utils import adb

KEYCODE_MAP = {
    "enter": "KEYCODE_ENTER",
    "return": "KEYCODE_ENTER",
    "esc": "KEYCODE_BACK",
    "escape": "KEYCODE_BACK",
    "back": "KEYCODE_BACK",
    "home": "KEYCODE_HOME",
    "menu": "KEYCODE_MENU",
    "tab": "KEYCODE_TAB",
    "space": "KEYCODE_SPACE",
    "backspace": "KEYCODE_DEL",
    "delete": "KEYCODE_DEL",
    "up": "KEYCODE_DPAD_UP",
    "down": "KEYCODE_DPAD_DOWN",
    "left": "KEYCODE_DPAD_LEFT",
    "right": "KEYCODE_DPAD_RIGHT",
    "center": "KEYCODE_DPAD_CENTER",
    "power": "KEYCODE_POWER",
    "volumeup": "KEYCODE_VOLUME_UP",
    "volumedown": "KEYCODE_VOLUME_DOWN",
}
"""dict: 按键名到 Android KEYCODE 名称的映射。"""

SWIPE_DURATION_MS = 300
"""int: 拖拽与滑动的默认时长（毫秒）。"""

SCROLL_PIXELS_PER_UNIT = 100
"""int: 一格滚动量对应的滑动像素数。"""


def _escape_text(text: str) -> str:
    """
    把待输入文本转换为 adb shell input text 可接受的格式（空格转 %s）。

    Args:
        text (str): 原始文本

    Returns:
        str: 转义后的文本
    """
    return text.replace(" ", "%s")


def perform(serial: str, action: Action) -> None:
    """
    对安卓设备执行一次输入动作。

    Args:
        serial (str): 设备序列号
        action (Action): 动作规格

    Raises:
        ActionError: 动作在安卓设备上不支持、参数缺失或执行失败时抛出
    """
    if action.kind == ACTION_CLICK:
        adb.run(["shell", "input", "tap", int(action.point[0]), int(action.point[1])],
                serial=serial)
    elif action.kind == ACTION_DOUBLE_CLICK:
        for _ in range(2):
            adb.run(["shell", "input", "tap", int(action.point[0]), int(action.point[1])],
                    serial=serial)
    elif action.kind == ACTION_DRAG:
        adb.run(["shell", "input", "swipe",
                 int(action.point[0]), int(action.point[1]),
                 int(action.end_point[0]), int(action.end_point[1]),
                 SWIPE_DURATION_MS], serial=serial)
    elif action.kind == ACTION_SCROLL:
        amount = int(action.text)
        delta = abs(amount) * SCROLL_PIXELS_PER_UNIT
        center_x = int(action.point[0])
        center_y = int(action.point[1])
        start_y = center_y + delta if amount > 0 else center_y - delta
        end_y = center_y - delta if amount > 0 else center_y + delta
        adb.run(["shell", "input", "swipe", center_x, start_y, center_x, end_y,
                 SWIPE_DURATION_MS], serial=serial)
    elif action.kind == ACTION_KEY:
        adb.run(["shell", "input", "keyevent", _keycode(action.text)], serial=serial)
    elif action.kind == ACTION_INPUT_TEXT:
        if not action.text.isascii():
            raise ActionError(
                f"adb_input.perform: adb shell input text 只支持 ASCII 文本，"
                f"待输入文本含非 ASCII 字符（{action.text!r}）；"
                f"安卓侧的中文输入需要设备上安装支持广播输入的输入法（如 ADBKeyboard）后扩展本模块"
            )
        adb.run(["shell", "input", "text", _escape_text(action.text)], serial=serial)
    elif action.kind == ACTION_RIGHT_CLICK:
        raise ActionError(
            f"adb_input.perform: 安卓触摸设备不支持右键点击（right_click），"
            f"设备={serial}；请改用长按或其它动作"
        )
    elif action.kind == ACTION_MOVE:
        raise ActionError(
            f"adb_input.perform: 安卓触摸设备没有鼠标悬停概念，不支持 move 动作，设备={serial}"
        )
    elif action.kind == ACTION_HOTKEY:
        raise ActionError(
            f"adb_input.perform: adb shell input 不支持组合键，hotkey 在安卓设备上不可用，"
            f"设备={serial}，请求组合键={action.text!r}；请改用单独的 key 动作"
        )
    else:
        raise ActionError(
            f"adb_input.perform: 未知动作类型 {action.kind!r}，可选值为 "
            f"{list(ACTION_KINDS)}"
        )


def _keycode(key: str) -> str:
    """
    把按键名转换为 Android KEYCODE 名称。

    Args:
        key (str): 按键名

    Returns:
        str: Android KEYCODE 名称

    Raises:
        ActionError: 未知按键名时抛出，消息含受支持的按键名列表
    """
    lowered = key.strip().lower()
    if lowered in KEYCODE_MAP:
        return KEYCODE_MAP[lowered]
    raise ActionError(
        f"input_adb._keycode: 未知按键名 {key!r}；安卓侧受支持的按键名为 {sorted(KEYCODE_MAP)}"
    )


class AdbInteraction(BaseInteraction):
    """
    安卓设备输入执行器。

    Attributes:
        kind (str): 固定为 KIND_DEVICE
        mode (str): 固定为 MODE_BACKGROUND，adb 输入不改变宿前台焦点
    """

    kind = KIND_DEVICE
    mode = MODE_BACKGROUND

    def execute(self, target, action: Action) -> None:
        """
        对安卓设备执行一次输入动作。

        Args:
            target (Target): 设备目标
            action (Action): 动作规格

        Raises:
            ActionError: 动作在安卓设备上不支持或执行失败时抛出
        """
        perform(target.id, action)
