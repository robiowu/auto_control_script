# -*- coding: utf-8 -*-
"""
errors.py - 异常类型模块

职责:
- 定义本项目统一的异常类型，每种异常带一个稳定的 code
- code 同时用于 CLI 退出码映射与 Web 接口的错误响应

调用链:
- 各能力模块 raise -> errors.py；cli.py / web/app.py 读取 code 做映射
"""


class AutoControlError(RuntimeError):
    """
    本项目所有业务异常的基类。

    Attributes:
        code (str): 稳定的错误标识，供 CLI 与 Web 映射使用
    """

    code = "AUTO_CONTROL_ERROR"


class TargetUnavailableError(AutoControlError):
    """目标不存在或已失效（窗口关闭、句柄失效、设备离线）。"""

    code = "TARGET_NOT_FOUND"


class CaptureError(AutoControlError):
    """截图失败，或取到的画面无效（全黑、单色、尺寸与窗口不符）。"""

    code = "CAPTURE_FAILED"


class ActionError(AutoControlError):
    """输入动作失败（目标失效、消息投递失败、设备拒绝）。"""

    code = "ACTION_FAILED"


class ChannelUnavailableError(AutoControlError):
    """指定的 OCR 通道或取图路径不可用，错误消息需说明缺少什么。"""

    code = "CHANNEL_UNAVAILABLE"


class DependencyMissingError(AutoControlError):
    """运行所需的前置依赖缺失（adb 不可用、可选包未安装）。"""

    code = "DEPENDENCY_MISSING"


class ScriptInvalidError(AutoControlError):
    """脚本参数非法、步骤引用无效或版本不受支持。"""

    code = "SCRIPT_INVALID"


class RunnerBusyError(AutoControlError):
    """同一目标上已有运行中的会话。"""

    code = "TARGET_BUSY"
