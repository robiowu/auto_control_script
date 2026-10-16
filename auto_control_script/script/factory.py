# -*- coding: utf-8 -*-
"""
script/factory.py - 脚本运行器工厂与对外入口模块

职责:
- 校验目标类型并按其创建对应的脚本运行器（工厂）
- 提供统一的运行器创建入口，避免上层直接依赖具体实现

调用链:
- cli.py / web/app.py -> script/factory.py -> script/runner.py

说明:
- 与 capture / interaction / ocr / matcher 等能力包保持一致的分包约定
"""

import logging

from auto_control_script.core import target as target_module
from auto_control_script.core.target import Target
from auto_control_script.script.base import BaseRunner

logger = logging.getLogger(__name__)


def create_runner(script, target: Target) -> BaseRunner:
    """
    创建脚本运行器（工厂方法）。

    Args:
        script: 待执行的脚本对象
        target (Target): 目标对象

    Returns:
        BaseRunner: 脚本运行器实例

    Raises:
        TargetUnavailableError: 目标类型非法时抛出
    """
    if target.kind not in (target_module.KIND_WINDOW, target_module.KIND_DEVICE):
        raise target_module.TargetUnavailableError(
            f"script.factory.create_runner: 目标类型非法 (kind={target.kind!r})，"
            f"可选值为 {[target_module.KIND_WINDOW, target_module.KIND_DEVICE]}"
        )
    from auto_control_script.script.runner import Runner

    logger.info(
        f"script.factory.create_runner: 创建运行器，脚本={script.name!r}，"
        f"目标={target.id}（{target.name!r}），类型={target.kind}"
    )
    return Runner(script, target)
