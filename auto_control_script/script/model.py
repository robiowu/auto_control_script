# -*- coding: utf-8 -*-
"""
script_model.py - 脚本与运行记录数据模型模块

职责:
- 定义 Script / Step / RunSession / StepRecord 四个数据结构
- 提供 JSON 序列化、反序列化与合法性校验

调用链:
- cli.py / runner.py / web/app.py -> script_model.py -> json / target.py

说明:
- 脚本以 JSON 文件持久化，导入导出即文件拷贝
- 校验在加载与保存时进行，非法脚本直接报错，不做猜测式修正
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional, Union

from auto_control_script.core import target as target_module
from auto_control_script.core.errors import ScriptInvalidError
from auto_control_script.core.settings import SETTINGS, scripts_dir

SCRIPT_VERSION = 1
"""int: 当前支持的脚本模型版本。"""

STEP_WAIT = "wait"
STEP_CAPTURE = "capture"
STEP_FIND_IMAGE = "find_image"
STEP_FIND_TEXT = "find_text"
STEP_CLICK = "click"
STEP_INPUT_TEXT = "input_text"
STEP_KEY = "key"
STEP_DRAG = "drag"
STEP_SCROLL = "scroll"
STEP_CONDITION = "condition"
STEP_LOOP = "loop"
STEP_LOG = "log"

STEP_TYPES = (
    STEP_WAIT, STEP_CAPTURE, STEP_FIND_IMAGE, STEP_FIND_TEXT, STEP_CLICK,
    STEP_INPUT_TEXT, STEP_KEY, STEP_DRAG, STEP_SCROLL, STEP_CONDITION,
    STEP_LOOP, STEP_LOG,
)
"""tuple: 全部合法的步骤类型。"""

FIND_STEP_TYPES = (STEP_FIND_IMAGE, STEP_FIND_TEXT)
"""tuple: 会产生定位结果、可被其它步骤引用的步骤类型。"""

FAIL_ABORT = "abort"
FAIL_CONTINUE = "continue"
FAIL_RETRY = "retry"

FAIL_POLICIES = (FAIL_ABORT, FAIL_CONTINUE, FAIL_RETRY)
"""tuple: 全部合法的失败策略。"""


@dataclass
class Step:
    """
    脚本中的一个步骤。

    Attributes:
        id (str): 步骤唯一标识，供其它步骤通过 ref 引用其定位结果
        type (str): 步骤类型，取 STEP_TYPES 之一
        enabled (bool): 是否参与运行
        params (dict): 类型相关参数
        ref (str): 引用的前序步骤 id，表示坐标来源
        on_fail (str): 失败策略，取 FAIL_POLICIES 之一
        timeout (float): 查找类步骤的超时秒数
        note (str): 备注
    """

    id: str
    type: str = STEP_WAIT
    enabled: bool = True
    params: dict = field(default_factory=dict)
    ref: Optional[str] = None
    on_fail: str = FAIL_ABORT
    timeout: float = 0.0
    note: str = ""


@dataclass
class Script:
    """
    一段可保存、可复用的自动化流程。

    Attributes:
        name (str): 脚本名
        version (int): 模型版本
        base_width (int): 基准分辨率宽度，用于在不同分辨率目标上换算坐标
        base_height (int): 基准分辨率高度
        target_kind (str): 适用的目标类型
        steps (list): 有序的 Step 列表
        options (dict): 全局运行配置
    """

    name: str = "未命名脚本"
    version: int = SCRIPT_VERSION
    base_width: int = 0
    base_height: int = 0
    target_kind: str = target_module.KIND_WINDOW
    steps: list = field(default_factory=list)
    options: dict = field(default_factory=dict)


@dataclass
class StepRecord:
    """
    一次运行中单个步骤的执行记录。

    Attributes:
        step_id (str): 步骤标识
        index (int): 步骤序号
        status (str): pending / running / success / failed / skipped
        duration (float): 耗时秒数
        snapshot_id (str): 关联的画面快照标识，无快照为 None
        error (str): 可读的失败原因，成功为 None
        detail (dict): 关键决策信息（取图路径、输入方式、OCR 通道等）
    """

    step_id: str
    index: int
    status: str = "pending"
    duration: float = 0.0
    snapshot_id: Optional[str] = None
    error: Optional[str] = None
    detail: dict = field(default_factory=dict)


@dataclass
class RunSession:
    """
    一次脚本执行过程。

    Attributes:
        id (str): 运行标识
        script_name (str): 脚本名
        target_id (str): 绑定目标标识
        state (str): idle / running / paused / stopped / succeeded / failed
        current_step_index (int): 当前执行到的步骤序号
        started_at (float): 开始时间戳
        finished_at (float): 结束时间戳，未结束为 None
        records (list): StepRecord 列表
        snapshots (list): 快照文件名列表
    """

    id: str
    script_name: str
    target_id: str = ""
    state: str = "idle"
    current_step_index: int = -1
    started_at: float = 0.0
    finished_at: Optional[float] = None
    records: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)


def new_script(name: str, target_kind: str = target_module.KIND_WINDOW) -> Script:
    """
    新建一个空脚本。

    Args:
        name (str): 脚本名
        target_kind (str): 适用目标类型

    Returns:
        Script: 新建的脚本对象
    """
    return Script(name=name, target_kind=target_kind)


def _step_to_dict(step: Step) -> dict:
    """
    把步骤转换为可序列化的字典。

    Args:
        step (Step): 步骤对象

    Returns:
        dict: 序列化后的字典
    """
    return {
        "id": step.id, "type": step.type, "enabled": step.enabled,
        "params": step.params, "ref": step.ref, "on_fail": step.on_fail,
        "timeout": step.timeout, "note": step.note,
    }


def _step_from_dict(data: dict) -> Step:
    """
    从字典还原步骤。

    Args:
        data (dict): 序列化后的步骤字典

    Returns:
        Step: 步骤对象
    """
    return Step(
        id=data.get("id") or "",
        type=data.get("type", STEP_WAIT),
        enabled=bool(data.get("enabled", True)),
        params=dict(data.get("params") or {}),
        ref=data.get("ref"),
        on_fail=data.get("on_fail", FAIL_ABORT),
        timeout=float(data.get("timeout", 0.0) or 0.0),
        note=data.get("note", ""),
    )


def to_dict(script: Script) -> dict:
    """
    把脚本转换为可序列化的字典。

    Args:
        script (Script): 脚本对象

    Returns:
        dict: 序列化后的字典
    """
    return {
        "name": script.name,
        "version": script.version,
        "base_width": script.base_width,
        "base_height": script.base_height,
        "target_kind": script.target_kind,
        "steps": [_step_to_dict(step) for step in script.steps],
        "options": script.options,
    }


def from_dict(data: dict) -> Script:
    """
    从字典还原脚本，并校验版本与步骤合法性。

    Args:
        data (dict): 序列化后的脚本字典

    Returns:
        Script: 脚本对象

    Raises:
        ScriptInvalidError: 版本高于当前支持版本，或步骤非法时抛出
    """
    version = int(data.get("version", SCRIPT_VERSION))
    if version > SCRIPT_VERSION:
        raise ScriptInvalidError(
            f"script_model.from_dict: 脚本版本 {version} 高于当前支持的 {SCRIPT_VERSION}，"
            f"请升级工具后再导入该脚本"
        )
    script = Script(
        name=data.get("name", "未命名脚本"),
        version=version,
        base_width=int(data.get("base_width", 0) or 0),
        base_height=int(data.get("base_height", 0) or 0),
        target_kind=data.get("target_kind", target_module.KIND_WINDOW),
        steps=[_step_from_dict(item) for item in data.get("steps", [])],
        options=dict(data.get("options") or {}),
    )
    errors = validate(script)
    if errors:
        raise ScriptInvalidError(
            f"script_model.from_dict: 脚本 {script.name!r} 校验未通过：\n" + "\n".join(errors)
        )
    return script


def validate(script: Script) -> list:
    """
    校验脚本合法性。

    校验项包括：步骤 id 唯一、步骤类型合法、失败策略合法、
    ref 指向存在且为查找类步骤。

    Args:
        script (Script): 待校验的脚本

    Returns:
        list: 错误描述列表，为空表示校验通过
    """
    errors = []
    seen = set()
    step_ids = set()
    for index, step in enumerate(script.steps):
        if not step.id:
            errors.append(f"第 {index + 1} 个步骤缺少 id")
        elif step.id in seen:
            errors.append(f"步骤 id {step.id!r} 重复")
        seen.add(step.id)
        if step.type not in STEP_TYPES:
            errors.append(
                f"步骤 {step.id!r} 的类型 {step.type!r} 非法，可选值为 {list(STEP_TYPES)}"
            )
        if step.on_fail not in FAIL_POLICIES:
            errors.append(
                f"步骤 {step.id!r} 的失败策略 {step.on_fail!r} 非法，"
                f"可选值为 {list(FAIL_POLICIES)}"
            )
    for step in script.steps:
        step_ids.add(step.id)
    for step in script.steps:
        if not step.ref:
            continue
        if step.ref not in step_ids:
            errors.append(f"步骤 {step.id!r} 引用了不存在的步骤 {step.ref!r}")
            continue
        referenced = next(item for item in script.steps if item.id == step.ref)
        if referenced.type not in FIND_STEP_TYPES:
            errors.append(
                f"步骤 {step.id!r} 引用了步骤 {step.ref!r}，但该步骤类型为 "
                f"{referenced.type!r}，不是查找类步骤 {list(FIND_STEP_TYPES)}，无法提供坐标"
            )
    return errors


def script_path(name: str) -> str:
    """
    获取脚本在用户目录下的文件路径。

    Args:
        name (str): 脚本名

    Returns:
        str: 脚本文件绝对路径
    """
    return os.path.join(scripts_dir(), f"{name}.json")


def save(script: Script, path: Optional[str] = None) -> str:
    """
    保存脚本到 JSON 文件。

    Args:
        script (Script): 脚本对象
        path (str): 保存路径，None 时保存到用户脚本目录

    Returns:
        str: 实际保存路径

    Raises:
        ScriptInvalidError: 脚本校验未通过时抛出
    """
    errors = validate(script)
    if errors:
        raise ScriptInvalidError(
            f"script_model.save: 脚本 {script.name!r} 校验未通过：\n" + "\n".join(errors)
        )
    path = path or script_path(script.name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(to_dict(script), file, ensure_ascii=False, indent=2)
    return path


def load(path: str) -> Script:
    """
    从 JSON 文件加载脚本。

    Args:
        path (str): 脚本文件路径

    Returns:
        Script: 脚本对象

    Raises:
        ScriptInvalidError: 文件不存在或内容非法时抛出
    """
    if not os.path.isfile(path):
        raise ScriptInvalidError(f"script_model.load: 脚本文件不存在 {path}")
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    return from_dict(data)


def export_script(script: Script, target_file: str) -> str:
    """
    导出脚本到指定文件（导入导出即文件拷贝）。

    Args:
        script (Script): 脚本对象
        target_file (str): 导出目标路径

    Returns:
        str: 导出路径
    """
    return save(script, target_file)


def max_runs() -> int:
    """
    获取运行记录的保留上限。

    Returns:
        int: 保留的运行记录条数上限
    """
    return int(SETTINGS["max_runs"])


def max_snapshots() -> int:
    """
    获取单次运行的快照保留上限。

    Returns:
        int: 单次运行保留的画面快照数量上限
    """
    return int(SETTINGS["max_snapshots_per_run"])


def snapshot_file(run_id: str, snapshot_id: str) -> str:
    """
    获取快照文件的绝对路径。

    Args:
        run_id (str): 运行标识
        snapshot_id (str): 快照标识

    Returns:
        str: 快照文件绝对路径
    """
    from auto_control_script.core.settings import runs_dir
    return os.path.join(runs_dir(), str(run_id), f"{snapshot_id}.jpg")


def list_scripts() -> list:
    """
    列出用户脚本目录下的全部脚本名。

    Returns:
        list: 脚本名列表（不含 .json 后缀）
    """
    directory = scripts_dir()
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.splitext(name)[0]
        for name in os.listdir(directory)
        if name.endswith(".json")
    )


def load_by_name(name: str) -> Script:
    """
    按脚本名从用户脚本目录加载脚本。

    Args:
        name (str): 脚本名

    Returns:
        Script: 脚本对象
    """
    return load(script_path(name))


def resolve_script(source: Union[str, Script]) -> Script:
    """
    把脚本名、脚本文件路径或脚本对象统一解析为脚本对象。

    Args:
        source (str | Script): 脚本名、脚本文件路径或脚本对象

    Returns:
        Script: 脚本对象
    """
    if isinstance(source, Script):
        return source
    if os.path.isfile(source):
        return load(source)
    return load_by_name(source)
