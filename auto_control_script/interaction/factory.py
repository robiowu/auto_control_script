# -*- coding: utf-8 -*-
"""
interaction/factory.py - 输入执行器工厂与对外入口模块

职责:
- 按目标类型与执行方式创建输入执行器（工厂）
- 提供 perform() 对外入口

调用链:
- cli.py / script/runner.py / web/app.py / case.py -> interaction/factory.py
    -> interaction/win_background.py / win_foreground.py / adb_input.py

分派方式:
- 窗口 + 后台 -> WinBackgroundInteraction（窗口消息，不抢焦点）
- 窗口 + 前台 -> WinForegroundInteraction（真实键鼠，会激活窗口）
- 设备        -> AdbInteraction（adb shell input）
"""

from auto_control_script.core import target as target_module
from auto_control_script.core.target import Target
from auto_control_script.interaction.base import (
    MODE_BACKGROUND, MODE_FOREGROUND, Action, BaseInteraction,
)


def create_interaction(target_kind: str, mode: str = MODE_BACKGROUND) -> BaseInteraction:
    """
    按目标类型与执行方式创建输入执行器（工厂方法）。

    Args:
        target_kind (str): 目标类型，取 core.target.KIND_WINDOW 或 KIND_DEVICE
        mode (str): 执行方式，MODE_BACKGROUND 或 MODE_FOREGROUND；
            安卓设备忽略该参数，一律走 adb

    Returns:
        BaseInteraction: 输入执行器实例

    Raises:
        ActionError: 执行方式非法时抛出
        TargetUnavailableError: 目标类型非法时抛出
    """
    if mode not in (MODE_BACKGROUND, MODE_FOREGROUND):
        from auto_control_script.core.errors import ActionError

        raise ActionError(
            f"interaction.factory.create_interaction: 未知执行方式 {mode!r}，"
            f"可选值为 {[MODE_BACKGROUND, MODE_FOREGROUND]}"
        )

    if target_kind == target_module.KIND_WINDOW:
        if mode == MODE_FOREGROUND:
            from auto_control_script.interaction.win_foreground import (
                WinForegroundInteraction,
            )

            return WinForegroundInteraction()
        from auto_control_script.interaction.win_background import WinBackgroundInteraction

        return WinBackgroundInteraction()

    if target_kind == target_module.KIND_DEVICE:
        from auto_control_script.interaction.adb_input import AdbInteraction

        return AdbInteraction()

    raise target_module.TargetUnavailableError(
        f"interaction.factory.create_interaction: 目标类型非法 (kind={target_kind!r})，"
        f"可选值为 {[target_module.KIND_WINDOW, target_module.KIND_DEVICE]}"
    )


def perform(target: Target, action: Action) -> None:
    """
    对目标执行一次输入动作。

    Args:
        target (Target): 目标对象
        action (Action): 动作规格，其 mode 决定后台还是前台

    Raises:
        ActionError: 动作非法、坐标缺失或越界、执行失败且重试耗尽时抛出
    """
    create_interaction(target.kind, action.mode).perform(target, action)
