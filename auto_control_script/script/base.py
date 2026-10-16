# -*- coding: utf-8 -*-
"""
script/base.py - 脚本运行器抽象基类模块

职责:
- 定义脚本运行器的统一接口，让上层（命令行 / 网页）依赖抽象而非具体实现

调用链:
- script/factory.py -> script/base.py -> script/runner.py

说明:
- 与其它能力包一致，本包固定提供 base.py（抽象）与 factory.py（分派）
"""

from abc import ABC, abstractmethod


class BaseRunner(ABC):
    """
    脚本运行器抽象基类。

    约定运行控制的统一接口：开始、暂停、继续、停止、结束判定、单步与重试本步。
    具体实现见 script/runner.py 的 Runner。
    """

    @abstractmethod
    def start(self) -> None:
        """
        开始运行，立即返回，执行在独立线程中进行。
        """

    @abstractmethod
    def pause(self) -> None:
        """
        暂停运行，在当前步骤结束后停住。
        """

    @abstractmethod
    def resume(self) -> None:
        """
        继续被暂停的运行。
        """

    @abstractmethod
    def stop(self, reason: str = "使用者主动停止") -> None:
        """
        停止运行。

        Args:
            reason (str): 停止原因，写入运行状态供使用者查看
        """

    @abstractmethod
    def is_finished(self) -> bool:
        """
        判断运行是否已结束。

        Returns:
            bool: 已结束为 True
        """

    @abstractmethod
    def step_once(self) -> dict:
        """
        单步执行一个步骤。

        Returns:
            dict: 运行状态字典
        """

    @abstractmethod
    def retry_step(self) -> dict:
        """
        重试当前步骤。

        Returns:
            dict: 运行状态字典
        """
