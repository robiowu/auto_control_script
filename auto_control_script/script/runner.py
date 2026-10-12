# -*- coding: utf-8 -*-
"""
runner.py - 脚本执行引擎模块

职责:
- 按步骤序列执行脚本，提供开始/暂停/继续/停止/单步/单步重试
- 记录逐步执行结果、耗时、失败原因与画面快照
- 在基准分辨率不同的目标上换算坐标并明确提示

调用链:
- cli.py / web/app.py -> runner.py -> capture.py / interaction.py / matcher.py / script_model.py
"""

import json
import logging
import os
import threading
import time
import uuid
from typing import Optional

from auto_control_script.capture import factory as capture
from auto_control_script.core import target as target_module
from auto_control_script.core.errors import AutoControlError, RunnerBusyError
from auto_control_script.core.frame import to_jpeg_bytes
from auto_control_script.core.settings import SETTINGS, runs_dir
from auto_control_script.interaction import factory as interaction
from auto_control_script.interaction.base import (
    ACTION_CLICK, ACTION_DRAG, ACTION_INPUT_TEXT, ACTION_KEY, ACTION_SCROLL, Action,
)
from auto_control_script.matcher import factory as matcher
from auto_control_script.script import model as script_model
from auto_control_script.script.model import (
    FAIL_ABORT, FAIL_CONTINUE, FAIL_RETRY, STEP_CAPTURE, STEP_CLICK, STEP_CONDITION,
    STEP_DRAG, STEP_FIND_IMAGE, STEP_FIND_TEXT, STEP_INPUT_TEXT, STEP_KEY, STEP_LOG,
    STEP_LOOP, STEP_SCROLL, STEP_WAIT,
)

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_STOPPED = "stopped"
STATE_SUCCEEDED = "succeeded"
STATE_FAILED = "failed"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

logger = logging.getLogger(__name__)

_RUNNING_TARGETS: set = set()
"""set: 当前有运行会话的目标标识，用于同目标互斥。"""


class Runner:
    """
    脚本执行器。

    一个执行器绑定一个脚本与一个目标；start() 在后台线程中顺序执行步骤，
    step_once() 用于调试时单步执行。

    Attributes:
        script (Script): 待执行的脚本
        target (Target): 绑定的目标
        session (RunSession): 本次运行的会话对象
    """

    def __init__(self, script, target):
        """
        初始化执行器。

        Args:
            script (Script): 待执行的脚本
            target (Target): 绑定的目标
        """
        self.script = script
        self.target = target
        self.session = script_model.RunSession(
            id=uuid.uuid4().hex[:12],
            script_name=script.name,
            target_id=target.id,
        )
        self._results: dict = {}
        self._loop_counters: dict = {}
        self._next_index = None
        self._thread = None
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._scaled_notice_sent = False
        self._snapshot_dir = os.path.join(runs_dir(), self.session.id)

    # ------------------------------------------------------------------ 运行控制

    def start(self) -> None:
        """
        启动后台线程开始执行脚本。

        Raises:
            RunnerBusyError: 该目标上已有运行中的会话时抛出
        """
        if self.target.id in _RUNNING_TARGETS:
            raise RunnerBusyError(
                f"runner.Runner.start: 目标 {self.target.id}（{self.target.name!r}）"
                f"上已有运行中的会话，不允许并发操作同一目标；"
                f"请先停止当前会话或换用其它目标"
            )
        _RUNNING_TARGETS.add(self.target.id)
        self.session.state = STATE_RUNNING
        self.session.started_at = time.time()
        os.makedirs(self._snapshot_dir, exist_ok=True)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"runner.Runner.start: 开始运行脚本 {self.script.name!r}，"
            f"目标={self.target.id}，会话={self.session.id}，步骤数={len(self.script.steps)}"
        )

    def pause(self) -> None:
        """请求暂停，实际在下一个步骤边界生效。"""
        self._pause_event.set()
        self.session.state = STATE_PAUSED
        self._persist()
        logger.info(f"runner.Runner.pause: 会话 {self.session.id} 已请求暂停")

    def resume(self) -> None:
        """从暂停处继续执行。"""
        self._pause_event.clear()
        self.session.state = STATE_RUNNING
        logger.info(f"runner.Runner.resume: 会话 {self.session.id} 继续运行")

    def stop(self, reason: str = "使用者主动停止") -> None:
        """
        请求停止，当前步骤结束后立即终止。

        Args:
            reason (str): 终止原因，写入会话记录
        """
        self._stop_event.set()
        self._pause_event.clear()
        self.session.state = STATE_STOPPED
        self.session.finished_at = time.time()
        for record in self.session.records:
            if record.status == STATUS_RUNNING:
                record.status = STATUS_FAILED
                record.error = reason
        self._persist()
        logger.info(f"runner.Runner.stop: 会话 {self.session.id} 已停止，原因={reason}")

    def is_finished(self) -> bool:
        """
        判断后台线程是否已结束。

        Returns:
            bool: 已结束返回 True
        """
        return self._thread is None or not self._thread.is_alive()

    def step_once(self) -> dict:
        """
        单步执行下一个未完成的步骤（调试用）。

        Returns:
            dict: 该步骤的执行记录字典
        """
        index = self.session.current_step_index + 1
        if index >= len(self.script.steps):
            return {"index": index, "status": "no_more_steps"}
        record = self._execute_index(index)
        return _record_to_dict(record)

    def retry_step(self) -> dict:
        """
        重试当前步骤（调试用）。

        Returns:
            dict: 该步骤的执行记录字典
        """
        index = max(self.session.current_step_index, 0)
        record = self._execute_index(index)
        return _record_to_dict(record)

    # ------------------------------------------------------------------ 内部执行

    def _run_loop(self) -> None:
        """后台线程的执行主循环。"""
        try:
            index = 0
            while index < len(self.script.steps):
                if self._stop_event.is_set():
                    break
                while self._pause_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.1)
                if self._stop_event.is_set():
                    break
                record = self._execute_index(index)
                if record.status == STATUS_FAILED:
                    policy = self.script.steps[index].on_fail
                    if policy == FAIL_ABORT:
                        self.session.state = STATE_FAILED
                        break
                if self._next_index is not None:
                    index = self._next_index
                    self._next_index = None
                    continue
                index += 1
            if self.session.state in (STATE_RUNNING, STATE_PAUSED):
                self.session.state = STATE_SUCCEEDED
        finally:
            self.session.finished_at = time.time()
            _RUNNING_TARGETS.discard(self.target.id)
            self._persist()
            logger.info(
                f"runner.Runner._run_loop: 会话 {self.session.id} 结束，"
                f"状态={self.session.state}"
            )

    def _execute_index(self, index: int):
        """
        执行指定序号的步骤并记录结果。

        Args:
            index (int): 步骤序号

        Returns:
            StepRecord: 该步骤的执行记录
        """
        step = self.script.steps[index]
        self.session.current_step_index = index
        record = script_model.StepRecord(step_id=step.id, index=index, status=STATUS_RUNNING)
        self.session.records = [item for item in self.session.records if item.index != index]
        self.session.records.append(record)
        self.session.records.sort(key=lambda item: item.index)
        record.status = STATUS_RUNNING

        if not step.enabled:
            record.status = STATUS_SKIPPED
            record.detail = {"reason": "步骤已停用"}
            self._persist()
            return record

        started = time.time()
        try:
            record.detail = self._dispatch_step(step)
            record.status = STATUS_SUCCESS
        except AutoControlError as error:
            record.status = STATUS_FAILED
            record.error = str(error)
            policy = step.on_fail
            if policy == FAIL_CONTINUE:
                logger.warning(
                    f"runner.Runner._execute_index: 步骤 {step.id!r} 失败但策略为继续，"
                    f"原因={error}"
                )
        record.duration = round(time.time() - started, 3)
        self._persist()
        logger.info(
            f"runner.Runner._execute_index: 步骤 {index + 1}/{len(self.script.steps)} "
            f"{step.id!r}({step.type}) -> {record.status}"
            f"{('，原因=' + record.error) if record.error else ''}"
        )
        return record

    def _dispatch_step(self, step) -> dict:
        """
        按步骤类型执行具体动作。

        Args:
            step (Step): 步骤对象

        Returns:
            dict: 关键决策信息，写入执行记录

        Raises:
            AutoControlError: 执行失败时抛出
        """
        params = step.params or {}
        if step.type == STEP_WAIT:
            seconds = float(params.get("seconds", 1.0))
            time.sleep(seconds)
            return {"seconds": seconds}

        if step.type == STEP_CAPTURE:
            frame = capture.capture(self.target, params.get("path"))
            return {"path": frame.path, "snapshot": self._save_snapshot(frame)}

        if step.type in (STEP_FIND_IMAGE, STEP_FIND_TEXT):
            return self._execute_find(step)

        if step.type == STEP_CLICK:
            point = self._resolve_point(step)
            action = Action(
                kind=ACTION_CLICK, point=point,
                mode=params.get("mode", SETTINGS["input_mode"]),
                wait_before=float(params.get("wait_before", 0.0)),
                retry=int(params.get("retry", 0)),
            )
            interaction.perform(self.target, action)
            return {"point": point, "mode": action.mode}

        if step.type == STEP_INPUT_TEXT:
            text = params.get("text")
            if not text:
                raise AutoControlError(
                    f"runner.Runner._dispatch_step: 步骤 {step.id!r} 缺少待输入文本 (params.text)"
                )
            point = self._resolve_point(step) if (step.ref or params.get("point")) else None
            if point:
                interaction.perform(self.target, Action(
                    kind=ACTION_CLICK, point=point,
                    mode=params.get("mode", SETTINGS["input_mode"])))
            action = Action(
                kind=ACTION_INPUT_TEXT, text=text,
                mode=params.get("mode", SETTINGS["input_mode"]),
            )
            interaction.perform(self.target, action)
            return {"text": text, "mode": action.mode}

        if step.type == STEP_KEY:
            action = Action(
                kind=ACTION_KEY, text=params.get("key"),
                mode=params.get("mode", SETTINGS["input_mode"]))
            interaction.perform(self.target, action)
            return {"key": params.get("key"), "mode": action.mode}

        if step.type == STEP_DRAG:
            start = self._resolve_point(step)
            end = self._scale_point(tuple(params.get("end_point")))
            action = Action(
                kind=ACTION_DRAG, point=start, end_point=end,
                mode=params.get("mode", SETTINGS["input_mode"]))
            interaction.perform(self.target, action)
            return {"point": start, "end_point": end, "mode": action.mode}

        if step.type == STEP_SCROLL:
            point = self._resolve_point(step)
            action = Action(
                kind=ACTION_SCROLL, point=point,
                text=str(params.get("amount", 0)),
                mode=params.get("mode", SETTINGS["input_mode"]))
            interaction.perform(self.target, action)
            return {"point": point, "amount": params.get("amount", 0), "mode": action.mode}

        if step.type == STEP_CONDITION:
            expect_found = bool(params.get("expect_found", True))
            actual = self._results.get(step.ref or params.get("ref"))
            satisfied = bool(actual and actual.found) == expect_found
            if satisfied and params.get("jump_to"):
                self._next_index = self._index_of(params["jump_to"])
                return {"satisfied": True, "jump_to": params["jump_to"]}
            return {"satisfied": satisfied}

        if step.type == STEP_LOOP:
            repeat = int(params.get("repeat", 1))
            counter = self._loop_counters.get(step.id, 0) + 1
            self._loop_counters[step.id] = counter
            if counter < repeat:
                self._next_index = self._index_of(params.get("from_step"))
                return {"round": counter, "repeat": repeat, "jump_back": True}
            return {"round": counter, "repeat": repeat, "jump_back": False}

        if step.type == STEP_LOG:
            message = params.get("message", "")
            logger.info(f"runner 脚本日志 [{self.script.name}] {message}")
            return {"message": message}

        raise AutoControlError(
            f"runner.Runner._dispatch_step: 未知步骤类型 {step.type!r}"
        )

    def _execute_find(self, step) -> dict:
        """
        执行查找类步骤，支持按超时反复查找直到命中。

        Args:
            step (Step): 查找类步骤

        Returns:
            dict: 查找结果信息

        Raises:
            AutoControlError: 超时仍未命中时抛出
        """
        params = step.params or {}
        deadline = time.monotonic() + float(step.timeout or 0.0)
        attempt = 0
        while True:
            attempt += 1
            frame = capture.capture(self.target, params.get("path"))
            if step.type == STEP_FIND_IMAGE:
                template = params.get("template")
                if not template:
                    raise AutoControlError(
                        f"runner.Runner._execute_find: 步骤 {step.id!r} 缺少模板路径 "
                        f"(params.template)"
                    )
                result = matcher.find_by_image(
                    frame, template, float(params.get("threshold", matcher.DEFAULT_THRESHOLD)))
            else:
                result = matcher.find_by_text(
                    frame, params.get("text"), lang=params.get("lang"),
                    channel=params.get("channel"), region=params.get("region"),
                    exact=bool(params.get("exact", False)))
            self._results[step.id] = result
            if result.found:
                return {
                    "found": True, "point": result.point, "box": result.box,
                    "score": result.score, "attempts": attempt,
                    "capture_path": frame.path, "detail": result.detail,
                }
            if step.on_fail != FAIL_RETRY or time.monotonic() >= deadline:
                raise AutoControlError(
                    f"runner.Runner._execute_find: 步骤 {step.id!r} 查找失败：{result.detail}"
                    f"（已尝试 {attempt} 次，超时设置={step.timeout}秒）"
                )
            time.sleep(float(params.get("retry_interval", 0.5)))

    def _index_of(self, step_id: str) -> int:
        """
        按步骤 id 查找其序号。

        Args:
            step_id (str): 步骤 id

        Returns:
            int: 步骤序号

        Raises:
            AutoControlError: 找不到该步骤时抛出
        """
        for index, step in enumerate(self.script.steps):
            if step.id == step_id:
                return index
        raise AutoControlError(
            f"runner.Runner._index_of: 脚本 {self.script.name!r} 中没有步骤 {step_id!r}"
        )

    def _resolve_point(self, step) -> tuple:
        """
        解析步骤的点击坐标：优先取引用步骤的定位结果，否则取步骤自带坐标。

        Args:
            step (Step): 步骤对象

        Returns:
            tuple: (x, y) 图像坐标

        Raises:
            AutoControlError: 无坐标且引用步骤未产生结果时抛出
        """
        if step.ref:
            result = self._results.get(step.ref)
            if result is None:
                raise AutoControlError(
                    f"runner.Runner._resolve_point: 步骤 {step.id!r} 引用了步骤 "
                    f"{step.ref!r}，但该步骤尚未执行或执行失败，无法提供坐标"
                )
            if not result.found or result.point is None:
                raise AutoControlError(
                    f"runner.Runner._resolve_point: 步骤 {step.ref!r} 未命中，"
                    f"步骤 {step.id!r} 无法取得坐标：{result.detail}"
                )
            return result.point
        point = (step.params or {}).get("point")
        if not point:
            raise AutoControlError(
                f"runner.Runner._resolve_point: 步骤 {step.id!r} 既没有引用 (ref) "
                f"也没有坐标 (params.point)，无法确定点击位置"
            )
        return self._scale_point(tuple(point))

    def _scale_point(self, point: tuple) -> tuple:
        """
        按基准分辨率换算坐标。

        Args:
            point (tuple): (x, y) 基于基准分辨率的坐标

        Returns:
            tuple: 换算到当前目标分辨率后的坐标
        """
        base_width = self.script.base_width
        base_height = self.script.base_height
        if not base_width or not base_height:
            return int(point[0]), int(point[1])
        target_module.refresh(self.target)
        if (base_width, base_height) == (self.target.width, self.target.height):
            return int(point[0]), int(point[1])
        ratio_x = self.target.width / base_width
        ratio_y = self.target.height / base_height
        if not self._scaled_notice_sent:
            self._scaled_notice_sent = True
            logger.warning(
                f"runner.Runner._scale_point: 脚本基准分辨率 {base_width}x{base_height} "
                f"与目标当前分辨率 {self.target.width}x{self.target.height} 不同，"
                f"坐标已按比例换算（x*{ratio_x:.4f}，y*{ratio_y:.4f}）"
            )
        return int(round(point[0] * ratio_x)), int(round(point[1] * ratio_y))

    def _save_snapshot(self, frame) -> str:
        """
        保存画面快照并返回快照标识。

        Args:
            frame (Frame): 画面帧

        Returns:
            str: 快照标识（不含扩展名），超出保留上限时返回 None
        """
        if len(self.session.snapshots) >= script_model.max_snapshots():
            return None
        snapshot_id = f"{len(self.session.snapshots):03d}"
        os.makedirs(self._snapshot_dir, exist_ok=True)
        path = os.path.join(self._snapshot_dir, f"{snapshot_id}.jpg")
        with open(path, "wb") as file:
            file.write(to_jpeg_bytes(frame))
        if snapshot_id not in self.session.snapshots:
            self.session.snapshots.append(snapshot_id)
        return snapshot_id

    def _persist(self) -> None:
        """把当前会话写入运行目录，便于页面重连后回看。"""
        os.makedirs(self._snapshot_dir, exist_ok=True)
        path = os.path.join(self._snapshot_dir, "session.json")
        with open(path, "w", encoding="utf-8") as file:
            json.dump(session_to_dict(self.session), file, ensure_ascii=False, indent=2)


def _record_to_dict(record) -> dict:
    """
    把执行记录转换为字典。

    Args:
        record (StepRecord): 执行记录

    Returns:
        dict: 序列化后的执行记录
    """
    return {
        "step_id": record.step_id, "index": record.index, "status": record.status,
        "duration": record.duration, "snapshot_id": record.snapshot_id,
        "error": record.error, "detail": record.detail,
    }


def session_to_dict(session) -> dict:
    """
    把运行会话转换为字典。

    Args:
        session (RunSession): 运行会话

    Returns:
        dict: 序列化后的运行会话
    """
    return {
        "id": session.id, "script_name": session.script_name, "target_id": session.target_id,
        "state": session.state, "current_step_index": session.current_step_index,
        "started_at": session.started_at, "finished_at": session.finished_at,
        "records": [_record_to_dict(item) for item in session.records],
        "snapshots": session.snapshots,
    }


def list_runs(target_id: Optional[str] = None) -> list:
    """
    列出历史运行记录，可按目标过滤。

    Args:
        target_id (str): 目标标识，None 时返回全部目标的运行记录

    Returns:
        list: 运行会话字典列表，按开始时间倒序
    """
    directory = runs_dir()
    if not os.path.isdir(directory):
        return []
    sessions = []
    for name in os.listdir(directory):
        path = os.path.join(directory, name, "session.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as file:
            sessions.append(json.load(file))
    if target_id is not None:
        sessions = [item for item in sessions if item.get("target_id") == target_id]
    sessions.sort(key=lambda item: item.get("started_at") or 0, reverse=True)
    return sessions


def cleanup_runs() -> int:
    """
    按保留上限清理最旧的运行记录。

    Returns:
        int: 被清理的运行记录条数
    """
    import shutil

    directory = runs_dir()
    if not os.path.isdir(directory):
        return 0
    runs = sorted(
        (name for name in os.listdir(directory)
         if os.path.isfile(os.path.join(directory, name, "session.json"))),
        key=lambda name: os.path.getmtime(os.path.join(directory, name)),
    )
    removed = 0
    while len(runs) > script_model.max_runs():
        shutil.rmtree(os.path.join(directory, runs.pop(0)))
        removed += 1
    return removed


def busy_targets() -> list:
    """
    获取当前有运行中会话的目标标识。

    Returns:
        list: 目标标识列表
    """
    return sorted(_RUNNING_TARGETS)
