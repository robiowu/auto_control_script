# -*- coding: utf-8 -*-
"""
interaction/base.py - 输入动作规格与执行器抽象基类模块

职责:
- 定义 Action：一次输入动作的规格
- 定义 BaseInteraction 抽象基类，并以模板方法统一校验、等待与重试

调用链:
- interaction/factory.py -> interaction/base.py -> core/target.py
- interaction/win_background.py / win_foreground.py / adb_input.py -> interaction/base.py

坐标约定:
- Action.point / end_point 使用图像坐标（与 Frame 像素坐标一致），
  由各平台实现内部换算为窗口消息坐标或屏幕坐标
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing import Optional
from auto_control_script.core import target as target_module
from auto_control_script.core.errors import ActionError
from auto_control_script.core.settings import SETTINGS
from auto_control_script.core.target import Target

MODE_BACKGROUND = "background"
"""str: 后台输入方式——不激活目标，不改变前台焦点与鼠标位置。"""

MODE_FOREGROUND = "foreground"
"""str: 前台输入方式——通过真实鼠标键盘完成动作，会激活目标窗口。"""

MODES = (MODE_BACKGROUND, MODE_FOREGROUND)
"""tuple: 全部合法的执行方式。"""

ACTION_CLICK = "click"
ACTION_DOUBLE_CLICK = "double_click"
ACTION_RIGHT_CLICK = "right_click"
ACTION_LONG_PRESS = "long_press"
ACTION_MOVE = "move"
ACTION_DRAG = "drag"
ACTION_SCROLL = "scroll"
ACTION_KEY = "key"
ACTION_HOTKEY = "hotkey"
ACTION_INPUT_TEXT = "input_text"

ACTION_KINDS = (
    ACTION_CLICK, ACTION_DOUBLE_CLICK, ACTION_RIGHT_CLICK, ACTION_LONG_PRESS,
    ACTION_MOVE, ACTION_DRAG, ACTION_SCROLL, ACTION_KEY, ACTION_HOTKEY,
    ACTION_INPUT_TEXT,
)
"""tuple: 全部合法的动作类型。"""

POINT_ACTIONS = (ACTION_CLICK, ACTION_DOUBLE_CLICK, ACTION_RIGHT_CLICK,
                 ACTION_LONG_PRESS, ACTION_MOVE, ACTION_DRAG, ACTION_SCROLL)
"""tuple: 需要坐标的动作类型。"""

LONG_PRESS_MS = 1000
"""int: 长按动作的默认持续毫秒数，可由 Action.text 覆盖。"""

TEXT_ACTIONS = (ACTION_SCROLL, ACTION_KEY, ACTION_HOTKEY, ACTION_INPUT_TEXT)
"""tuple: 需要文本参数的动作类型。"""

logger = logging.getLogger(__name__)


@dataclass
class Action:
    """
    一次输入动作的规格。

    Attributes:
        kind (str): 动作类型，取 ACTION_KINDS 之一
        point (tuple): (x, y) 图像坐标；拖拽时为起点，滚动时表示滚动位置
        end_point (tuple): 拖拽终点，仅 drag 需要
        text (str): 输入文本（input_text）、按键名（key / hotkey，组合键用 "+" 连接），
            或长按动作的持续毫秒数（long_press，省略时取 LONG_PRESS_MS）
        mode (str): 执行方式，MODE_BACKGROUND 或 MODE_FOREGROUND
        wait_before (float): 动作前的等待秒数
        jitter (float): 在等待基础上附加的随机抖动秒数，0 表示不抖动
        retry (int): 失败后的重试次数，0 表示不重试
        retry_interval (float): 重试之间的间隔秒数
    """

    kind: str
    point: Optional[tuple] = None
    end_point: Optional[tuple] = None
    text: Optional[str] = None
    mode: str = field(default_factory=lambda: SETTINGS["input_mode"])
    wait_before: float = 0.0
    jitter: float = 0.0
    retry: int = 0
    retry_interval: float = 0.5


class BaseInteraction(ABC):
    """
    平台输入执行器抽象基类。

    子类声明 kind 与 mode 并实现 execute()；基类以模板方法 perform()
    统一完成动作校验、坐标校验、等待抖动与失败重试。

    Attributes:
        kind (str): 适用的目标类型，取 core.target.KIND_* 之一
        mode (str): 执行方式，取 MODE_BACKGROUND 或 MODE_FOREGROUND
    """

    kind: str = ""
    """str: 适用的目标类型，子类覆盖。"""

    mode: str = MODE_BACKGROUND
    """str: 执行方式，子类覆盖。"""

    @abstractmethod
    def execute(self, target: Target, action: Action) -> None:
        """
        执行一次输入动作（平台特有实现）。

        Args:
            target (Target): 目标对象
            action (Action): 动作规格
        """

    def _validate_point(self, target: Target, action: Action, name: str, point: tuple) -> None:
        """
        校验坐标落在目标范围内。

        Args:
            target (Target): 目标对象
            action (Action): 动作对象，用于错误信息
            name (str): 坐标含义（起点/终点），用于错误信息
            point (tuple): 待校验的坐标

        Raises:
            ActionError: 坐标缺失或越界时抛出
        """
        if point is None:
            raise ActionError(
                f"interaction.base.BaseInteraction._validate_point: 动作 {action.kind} "
                f"缺少{name}，动作={action}"
            )
        x, y = point
        if x < 0 or y < 0 or x > target.width or y > target.height:
            raise ActionError(
                f"interaction.base.BaseInteraction._validate_point: 动作 {action.kind} 的{name} "
                f"({x}, {y}) 超出目标 {target.id}（{target.name!r}）的范围 "
                f"{target.width}x{target.height}"
            )

    def _validate_action(self, action: Action) -> None:
        """
        校验动作类型、执行方式与必需参数。

        Args:
            action (Action): 动作规格

        Raises:
            ActionError: 取值非法或缺少必需参数时抛出
        """
        if action.kind not in ACTION_KINDS:
            raise ActionError(
                f"interaction.base.BaseInteraction._validate_action: 未知动作类型 "
                f"{action.kind!r}，可选值为 {list(ACTION_KINDS)}"
            )
        if action.mode not in MODES:
            raise ActionError(
                f"interaction.base.BaseInteraction._validate_action: 未知执行方式 "
                f"{action.mode!r}，可选值为 {list(MODES)}"
            )
        if action.kind in TEXT_ACTIONS and not action.text:
            role = {"scroll": "滚动量", "key": "按键名", "hotkey": "组合键",
                    "input_text": "待输入文本"}[action.kind]
            raise ActionError(
                f"interaction.base.BaseInteraction._validate_action: 动作 "
                f"{action.kind} 缺少{role}（text）"
            )

    def perform(self, target: Target, action: Action) -> None:
        """
        校验并执行一次输入动作（模板方法）。

        依次完成：动作校验 -> 目标刷新 -> 坐标校验 -> 等待抖动 -> 执行并重试。

        Args:
            target (Target): 目标对象
            action (Action): 动作规格

        Raises:
            ActionError: 动作非法、坐标缺失或越界、执行失败且重试耗尽时抛出
        """
        self._validate_action(action)
        target_module.refresh(target)
        if action.point is not None:
            self._validate_point(target, action, "起点", action.point)
        if action.kind == ACTION_DRAG:
            self._validate_point(target, action, "终点", action.end_point)

        delay = action.wait_before + (random.uniform(0, action.jitter) if action.jitter else 0.0)
        time.sleep(delay)

        attempts = action.retry + 1
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                self.execute(target, action)
                logger.info(
                    f"interaction.base.BaseInteraction.perform: 动作完成，目标={target.id}，"
                    f"类型={action.kind}，方式={self.mode}，坐标={action.point}，"
                    f"第 {attempt}/{attempts} 次尝试"
                )
                return
            except ActionError as error:
                last_error = error
                logger.warning(
                    f"interaction.base.BaseInteraction.perform: 动作失败，目标={target.id}，"
                    f"类型={action.kind}，第 {attempt}/{attempts} 次尝试，原因={error}"
                )
                if attempt < attempts:
                    time.sleep(action.retry_interval)
        raise ActionError(
            f"interaction.base.BaseInteraction.perform: 动作 {action.kind} 在目标 "
            f"{target.id}（{target.name!r}）上重试 {action.retry} 次后仍失败，"
            f"最后一次失败原因：{last_error}"
        )
