# -*- coding: utf-8 -*-
"""
interaction/key_codes.py - 按键名到虚拟键码的映射模块

职责:
- 提供按键名（如 enter、f5）到 Windows 虚拟键码的映射
- 单个字符回退到系统键盘布局查询

调用链:
- interaction/win_background.py -> interaction/key_codes.py -> win32api / win32con
"""

import win32api
import win32con

from auto_control_script.core.errors import ActionError

VK_MAP = {
    "enter": win32con.VK_RETURN,
    "return": win32con.VK_RETURN,
    "esc": win32con.VK_ESCAPE,
    "escape": win32con.VK_ESCAPE,
    "tab": win32con.VK_TAB,
    "space": win32con.VK_SPACE,
    "backspace": win32con.VK_BACK,
    "delete": win32con.VK_DELETE,
    "home": win32con.VK_HOME,
    "end": win32con.VK_END,
    "pageup": win32con.VK_PRIOR,
    "pagedown": win32con.VK_NEXT,
    "up": win32con.VK_UP,
    "down": win32con.VK_DOWN,
    "left": win32con.VK_LEFT,
    "right": win32con.VK_RIGHT,
    "ctrl": win32con.VK_CONTROL,
    "shift": win32con.VK_SHIFT,
    "alt": win32con.VK_MENU,
    "win": win32con.VK_LWIN,
    "capslock": win32con.VK_CAPITAL,
    "insert": win32con.VK_INSERT,
    "printscreen": win32con.VK_SNAPSHOT,
}
"""dict: 按键名到虚拟键码的映射。"""

for _index in range(1, 25):
    VK_MAP[f"f{_index}"] = getattr(win32con, f"VK_F{_index}")


def get_vk_code(key: str) -> int:
    """
    把按键名或单字符转换为虚拟键码。

    Args:
        key (str): 按键名（如 "enter"）或单个字符（如 "a"）

    Returns:
        int: 虚拟键码

    Raises:
        ActionError: 无法解析时抛出，消息含已知按键名列表
    """
    lowered = key.strip().lower()
    if lowered in VK_MAP:
        return VK_MAP[lowered]
    if len(lowered) == 1:
        result = win32api.VkKeyScan(lowered)
        if result == -1:
            raise ActionError(
                f"interaction.key_codes.get_vk_code: 无法把字符 {key!r} 转换为虚拟键码；"
                f"可改用已知按键名 {sorted(VK_MAP)}"
            )
        return result & 0xFF
    raise ActionError(
        f"interaction.key_codes.get_vk_code: 未知按键名 {key!r}；"
        f"单个字符请直接传入该字符，其余请使用 {sorted(VK_MAP)} 中的按键名"
    )
