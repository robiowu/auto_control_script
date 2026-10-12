# -*- coding: utf-8 -*-
"""
settings.py - 配置与用户目录模块

职责:
- 集中存放全部默认配置，并支持用用户目录下的 settings.json 覆盖
- 提供脚本、运行记录、日志三类用户目录的绝对路径

调用链:
- capture.py / ocr.py / interaction.py / runner.py -> settings.py -> os / json

注意:
- 本文件不得改名为 config.py，仓库根目录的 .gitignore 忽略了 config.py
"""

import json
import os

APP_NAME = "auto_control_script"

# 默认值：用户目录下的 settings.json 只需写要覆盖的键
DEFAULT_SETTINGS = {
    # ADB 可执行文件；在 PATH 中时为 "adb"，否则填绝对路径
    "adb_path": "adb",
    # 截图：窗口目标的取图路径 auto / wgc / printwindow / bitblt
    "capture_path": "auto",
    # OCR：通道 auto / builtin / precise，语言见 ocr.py 的语言表
    "ocr_channel": "auto",
    "ocr_language": "ch",
    # 输入：默认后台（不激活目标、不抢焦点）
    "input_mode": "background",
    # 动作节奏（秒）与随机抖动（秒）
    "click_delay": 0.05,
    "type_delay": 0.05,
    "move_delay": 0.1,
    "jitter": 0.02,
    # 运行记录保留上限，超出后按最旧优先清理
    "max_runs": 20,
    "max_snapshots_per_run": 200,
    # 网页服务：仅监听本机回环地址
    "web_host": "127.0.0.1",
    "web_port": 8770,
}


def user_dir() -> str:
    """
    获取本项目的用户数据根目录（%APPDATA%/auto_control_script）。

    Returns:
        str: 用户数据根目录的绝对路径
    """
    appdata = os.getenv("APPDATA")
    if not appdata:
        raise RuntimeError(
            f"settings.user_dir: APPDATA 环境变量未设置，无法确定用户数据根目录 "
            f"(APPDATA={appdata!r})"
        )
    return os.path.join(appdata, APP_NAME)


def scripts_dir() -> str:
    """
    获取脚本存放目录。

    Returns:
        str: 脚本目录的绝对路径
    """
    return os.path.join(user_dir(), "scripts")


def runs_dir() -> str:
    """
    获取运行记录与快照存放目录。

    Returns:
        str: 运行记录目录的绝对路径
    """
    return os.path.join(user_dir(), "runs")


def logs_dir() -> str:
    """
    获取日志存放目录。

    Returns:
        str: 日志目录的绝对路径
    """
    return os.path.join(user_dir(), "logs")


def ensure_dirs() -> None:
    """创建脚本、运行记录、日志三个用户目录，已存在时不做任何事。"""
    for path in (scripts_dir(), runs_dir(), logs_dir()):
        os.makedirs(path, exist_ok=True)


def load_settings() -> dict:
    """
    读取配置：以 DEFAULT_SETTINGS 为底，用用户目录下的 settings.json 覆盖。

    settings.json 不存在时直接返回默认值；存在但含未知键时报错，
    避免把拼错的键当成"未设置"而静默使用默认值。

    Returns:
        dict: 合并后的配置字典
    """
    merged = dict(DEFAULT_SETTINGS)
    config_path = os.path.join(user_dir(), "settings.json")
    if not os.path.isfile(config_path):
        return merged
    with open(config_path, encoding="utf-8") as file:
        override = json.load(file)
    unknown = [key for key in override if key not in DEFAULT_SETTINGS]
    if unknown:
        raise RuntimeError(
            f"settings.load_settings: settings.json 含未知配置键 {unknown}，"
            f"可选键为 {sorted(DEFAULT_SETTINGS)}，配置文件路径={config_path}"
        )
    merged.update(override)
    return merged


SETTINGS: dict = load_settings()
"""dict: 进程级配置，由默认值与用户 settings.json 合并而来。"""
