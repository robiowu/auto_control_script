# -*- coding: utf-8 -*-
"""
adb.py - ADB 命令行通道模块

职责:
- 统一执行 adb 命令（文本输出与字节输出两类）
- 枚举已连接设备、建立网络连接

调用链:
- target.py / capture_adb.py / input_adb.py -> adb.py -> subprocess

说明:
- 全部命令以参数列表方式调用，不使用 shell=True，避免命令行转义问题
- 多设备通过 -s <serial> 区分
"""

import subprocess

from typing import Optional
from auto_control_script.core.errors import AutoControlError, DependencyMissingError
from auto_control_script.core.settings import SETTINGS

DEFAULT_TIMEOUT = 20.0
"""float: adb 命令默认超时时间（秒）。"""


def adb_executable() -> str:
    """
    获取 adb 可执行文件路径。

    Returns:
        str: settings 中配置的 adb 路径
    """
    return SETTINGS["adb_path"]


def build_command(args: list, serial: Optional[str] = None) -> list:
    """
    拼装完整的 adb 命令行参数列表。

    Args:
        args (list): adb 子命令参数，如 ["shell", "input", "tap", "10", "20"]
        serial (str): 设备序列号，为空时不加 -s 参数

    Returns:
        list: 完整命令行参数列表
    """
    command = [adb_executable()]
    if serial:
        command += ["-s", serial]
    command += [str(item) for item in args]
    return command


def run(args: list, serial: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> str:
    """
    执行 adb 命令并返回标准输出的文本内容。

    Args:
        args (list): adb 子命令参数
        serial (str): 设备序列号
        timeout (float): 超时时间（秒）

    Returns:
        str: 标准输出内容（已去除首尾空白）

    Raises:
        DependencyMissingError: adb 可执行文件不存在时抛出
        AutoControlError: 命令返回非零退出码时抛出，消息含完整命令与输出
    """
    command = build_command(args, serial)
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
    except FileNotFoundError as error:
        raise DependencyMissingError(
            f"adb.run: 找不到 adb 可执行文件 {adb_executable()!r}，"
            f"请确认 adb 已安装并在 PATH 中，或在 settings.json 中配置 adb_path 为绝对路径"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise AutoControlError(
            f"adb.run: 命令执行超时（{timeout}秒）：{' '.join(command)}"
        ) from error
    output = result.stdout.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        error_output = result.stderr.decode("utf-8", errors="replace").strip()
        raise AutoControlError(
            f"adb.run: 命令执行失败（退出码={result.returncode}）：{' '.join(command)}，"
            f"stdout={output!r}，stderr={error_output!r}"
        )
    return output


def run_bytes(args: list, serial: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """
    执行 adb 命令并返回标准输出的原始字节，用于获取截图二进制。

    Args:
        args (list): adb 子命令参数
        serial (str): 设备序列号
        timeout (float): 超时时间（秒）

    Returns:
        bytes: 标准输出的原始字节

    Raises:
        DependencyMissingError: adb 可执行文件不存在时抛出
        AutoControlError: 命令返回非零退出码或输出为空时抛出
    """
    command = build_command(args, serial)
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
    except FileNotFoundError as error:
        raise DependencyMissingError(
            f"adb.run_bytes: 找不到 adb 可执行文件 {adb_executable()!r}，"
            f"请确认 adb 已安装并在 PATH 中，或在 settings.json 中配置 adb_path 为绝对路径"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise AutoControlError(
            f"adb.run_bytes: 命令执行超时（{timeout}秒）：{' '.join(command)}"
        ) from error
    if result.returncode != 0:
        error_output = result.stderr.decode("utf-8", errors="replace").strip()
        raise AutoControlError(
            f"adb.run_bytes: 命令执行失败（退出码={result.returncode}）：{' '.join(command)}，"
            f"stderr={error_output!r}"
        )
    if not result.stdout:
        raise AutoControlError(
            f"adb.run_bytes: 命令无输出：{' '.join(command)}"
        )
    return result.stdout


def list_devices() -> list:
    """
    枚举当前已连接的安卓设备。

    Returns:
        list: 设备信息列表，每项为 dict，含 serial、state、product 三个键

    Raises:
        DependencyMissingError: adb 不可用时抛出
    """
    output = run(["devices", "-l"])
    devices = []
    started = False
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("List of devices"):
            started = True
            continue
        if not started:
            continue
        parts = line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        product = ""
        for part in parts[2:]:
            if part.startswith("model:"):
                product = part.split(":", 1)[1].replace("_", " ")
                break
        devices.append({"serial": serial, "state": state, "product": product})
    return devices


def connect(serial: str) -> None:
    """
    通过网络连接（IP:端口）方式建立 adb 连接。

    Args:
        serial (str): 形如 "127.0.0.1:16448" 的设备地址

    Raises:
        AutoControlError: 连接失败时抛出
    """
    output = run(["connect", serial])
    if "connected to" not in output and "already connected" not in output:
        raise AutoControlError(
            f"adb.connect: 连接设备 {serial} 未成功，adb 输出={output!r}"
        )
