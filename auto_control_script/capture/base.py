# -*- coding: utf-8 -*-
"""
capture/base.py - 截图器抽象基类模块

职责:
- 定义 BaseCapture 抽象基类，约定平台截图器必须实现的能力
- 提供各平台共用的取图路径校验与目标可用性校验

调用链:
- capture/factory.py -> capture/base.py -> core/target.py

路径约定:
- 每个平台自己声明支持的取图路径，基类据此校验，非法取值直接报错
"""

from abc import ABC, abstractmethod

from typing import Optional
from auto_control_script.core import target as target_module
from auto_control_script.core.errors import ChannelUnavailableError
from auto_control_script.core.frame import Frame
from auto_control_script.core.target import Target

PATH_AUTO = "auto"
"""str: 取图路径——自动选择，由各平台按自身顺序择优。"""


class BaseCapture(ABC):
    """
    平台截图器抽象基类。

    子类声明 kind 与 paths，实现 grab()；基类负责校验路径与目标可用性。

    Attributes:
        kind (str): 适用的目标类型，取 core.target.KIND_* 之一
        paths (tuple): 本平台支持的取图路径
    """

    kind: str = ""
    """str: 适用的目标类型，子类覆盖。"""

    paths: tuple = ()
    """tuple: 本平台支持的取图路径，子类覆盖。"""

    @abstractmethod
    def grab(self, target: Target, path: str) -> Frame:
        """
        按指定路径截取目标画面。

        Args:
            target (Target): 目标对象
            path (str): 取图路径，已通过 validate_path 校验

        Returns:
            Frame: 画面帧
        """

    def release(self, target: Optional[Target] = None) -> None:
        """
        释放取图资源，默认无需释放。

        Args:
            target (Target): 目标对象，None 表示释放全部
        """

    def validate_path(self, target: Target, path: str) -> str:
        """
        校验取图路径对本平台是否合法。

        Args:
            target (Target): 目标对象，用于错误信息
            path (str): 取图路径

        Returns:
            str: 校验通过的路径

        Raises:
            ChannelUnavailableError: 路径不合法时抛出
        """
        if path not in self.paths:
            raise ChannelUnavailableError(
                f"capture.base.BaseCapture.validate_path: {self.kind} 目标 "
                f"{target.id}（{target.name!r}）不支持取图路径 {path!r}，"
                f"该目标类型可选值为 {list(self.paths)}"
            )
        return path

    def capture(self, target: Target, path: str) -> Frame:
        """
        校验目标与路径后执行取图。

        Args:
            target (Target): 目标对象
            path (str): 取图路径

        Returns:
            Frame: 画面帧

        Raises:
            ChannelUnavailableError: 路径不合法时抛出
        """
        self.validate_path(target, path)
        target_module.require_available(target, f"截图（路径={path}）")
        return self.grab(target, path)
