# -*- coding: utf-8 -*-
"""
web/app.py - Web 服务端模块

职责:
- 提供目标查询、画面预览、OCR、查找、脚本管理、运行控制的 HTTP 接口
- 以 SSE 单向推送运行状态与逐步日志
- 把业务异常统一转换为带 code 的错误响应

调用链:
- cli.py -> web/app.py -> target.py / capture.py / ocr.py / matcher.py / runner.py
- 浏览器 -> web/app.py -> web/static/ 前端页面

说明:
- 仅监听本机回环地址，定位为单机使用，不含账号与权限体系
"""

import functools
import json
import logging
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from typing import Optional
from auto_control_script.capture import factory as capture
from auto_control_script.core import target as target_module
from auto_control_script.core.errors import AutoControlError
from auto_control_script.core.frame import to_jpeg_bytes
from auto_control_script.core.settings import SETTINGS, ensure_dirs, runs_dir, scripts_dir
from auto_control_script.interaction import factory as interaction
from auto_control_script.interaction.base import Action
from auto_control_script.matcher import factory as matcher
from auto_control_script.ocr import factory as ocr
from auto_control_script.script import factory as script_factory
from auto_control_script.script import model as script_model
from auto_control_script.script import runner

logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
"""str: 前端静态资源目录。"""

_RUNNERS: dict = {}
"""dict: 运行标识 -> Runner 的注册表。"""

app = FastAPI(title="auto_control_script", description="统一截图·输入·OCR 自动化平台")


# ------------------------------------------------------------------ 数据契约


class OcrRequest(BaseModel):
    """OCR 请求体。"""

    target_id: str
    region: Optional[list] = None
    lang: Optional[str] = None
    channel: Optional[str] = None
    path: Optional[str] = None


class FindRequest(BaseModel):
    """查找请求体。"""

    target_id: str
    by: str = "text"
    text: Optional[str] = None
    template: Optional[str] = None
    threshold: float = matcher.DEFAULT_THRESHOLD
    region: Optional[list] = None
    lang: Optional[str] = None
    channel: Optional[str] = None
    path: Optional[str] = None


class InputRequest(BaseModel):
    """输入动作请求体。"""

    target_id: str
    action: str
    point: Optional[list] = None
    end_point: Optional[list] = None
    text: Optional[str] = None
    mode: Optional[str] = None


class ScriptPayload(BaseModel):
    """脚本保存请求体。"""

    script: dict
    name: Optional[str] = None


class RunRequest(BaseModel):
    """运行请求体。"""

    script: str
    target_id: str
    from_step: int = 0


# ------------------------------------------------------------------ 工具


def _resolve(target_id: str):
    """
    按标识解析目标。

    Args:
        target_id (str): 目标标识

    Returns:
        Target: 目标对象
    """
    return target_module.resolve_target(target_id)


def _error_response(error: AutoControlError) -> JSONResponse:
    """
    把业务异常转换为错误响应。

    Args:
        error (AutoControlError): 业务异常

    Returns:
        JSONResponse: 含 code 与 message 的错误响应
    """
    return JSONResponse(
        status_code=400,
        content={"error": {"code": error.code, "message": str(error)}},
    )


def _guard(func):
    """
    包装接口函数，把业务异常转换为错误响应。

    Args:
        func: 被包装的接口函数

    Returns:
        包装后的函数
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AutoControlError as error:
            logger.warning(f"web.app: 接口返回业务错误 code={error.code} message={error}")
            return _error_response(error)
    return wrapper


def _frame_response(target_id: str, region: list, path: str) -> Response:
    """
    取画面并返回 JPEG 响应。

    Args:
        target_id (str): 目标标识
        region (list): 区域 [x1, y1, x2, y2]
        path (str): 取图路径

    Returns:
        Response: JPEG 图像响应
    """
    target = _resolve(target_id)
    frame = (capture.capture_region(target, tuple(region), path) if region
             else capture.capture(target, path))
    return Response(content=to_jpeg_bytes(frame), media_type="image/jpeg")


# ------------------------------------------------------------------ 目标与画面


@app.get("/api/targets")
@_guard
def list_targets(kind: str = "all"):
    """列出可用目标。"""
    return [{
        "kind": item.kind, "id": item.id, "name": item.name,
        "width": item.width, "height": item.height, "available": item.available,
        "visible": item.visible, "meta": item.meta,
    } for item in target_module.list_targets(kind)]


@app.get("/api/targets/{target_id}/frame.jpg")
@_guard
def target_frame(target_id: str, region: Optional[str] = None, path: Optional[str] = None):
    """获取目标当前画面的 JPEG。region 形如 x1,y1,x2,y2。"""
    parsed = [int(item) for item in region.split(",")] if region else None
    return _frame_response(target_id, parsed, path)


@app.get("/api/targets/{target_id}/frame/meta")
@_guard
def target_frame_meta(target_id: str, path: Optional[str] = None):
    """获取目标画面的元信息（尺寸、实际取图路径、采集时间）。"""
    target = _resolve(target_id)
    frame = capture.capture(target, path)
    return {
        "width": frame.width, "height": frame.height,
        "path": frame.path, "captured_at": frame.captured_at, "origin": frame.origin,
    }


# ------------------------------------------------------------------ OCR 与查找


@app.get("/api/ocr/channels")
@_guard
def ocr_channels():
    """查询两类 OCR 通道的可用状态与缺失的前置条件。"""
    return ocr.channel_status()


@app.post("/api/ocr")
@_guard
def run_ocr(request: OcrRequest):
    """对目标画面做 OCR。"""
    target = _resolve(request.target_id)
    region = tuple(request.region) if request.region else None
    frame = (capture.capture_region(target, region, request.path) if region
             else capture.capture(target, request.path))
    if region:
        result = ocr.recognize_region(frame, region, lang=request.lang, channel=request.channel)
    else:
        result = ocr.recognize(frame, lang=request.lang, channel=request.channel)
    return {
        "channel": result.channel, "channel_reason": result.channel_reason,
        "confidence_available": result.confidence_available, "language": result.language,
        "region": result.region,
        "items": [{
            "text": item.text, "box": list(item.box),
            "confidence": item.confidence, "order": item.order,
        } for item in result.items],
    }


@app.post("/api/find")
@_guard
def run_find(request: FindRequest):
    """按图或按字查找目标位置。"""
    target = _resolve(request.target_id)
    frame = capture.capture(target, request.path)
    if request.by == "image":
        result = matcher.find_by_image(frame, request.template, threshold=request.threshold)
    else:
        result = matcher.find_by_text(
            frame, request.text, lang=request.lang, channel=request.channel,
            region=tuple(request.region) if request.region else None)
    return {
        "found": result.found, "kind": result.kind,
        "point": list(result.point) if result.point else None,
        "box": list(result.box) if result.box else None,
        "score": result.score, "detail": result.detail,
    }


# ------------------------------------------------------------------ 输入


@app.post("/api/input")
@_guard
def perform_input(request: InputRequest):
    """对目标下发一次输入动作。"""
    target = _resolve(request.target_id)
    action = Action(
        kind=request.action,
        point=tuple(request.point) if request.point else None,
        end_point=tuple(request.end_point) if request.end_point else None,
        text=request.text,
        mode=request.mode or SETTINGS["input_mode"],
    )
    interaction.perform(target, action)
    return {"target_id": target.id, "action": action.kind, "mode": action.mode}


# ------------------------------------------------------------------ 脚本


@app.get("/api/scripts")
@_guard
def list_scripts():
    """列出全部脚本。"""
    return script_model.list_scripts()


@app.get("/api/scripts/{name}")
@_guard
def read_script(name: str):
    """读取脚本内容。"""
    with open(script_model.script_path(name), encoding="utf-8") as file:
        return json.load(file)


@app.post("/api/scripts")
@_guard
def create_script(payload: ScriptPayload):
    """新建脚本。"""
    script = script_model.from_dict(payload.script)
    script.name = payload.name or script.name
    path = script_model.save(script)
    return {"name": script.name, "path": path}


@app.put("/api/scripts/{name}")
@_guard
def save_script(name: str, payload: ScriptPayload):
    """保存脚本。"""
    script = script_model.from_dict(payload.script)
    script.name = payload.name or name
    path = script_model.save(script)
    return {"name": script.name, "path": path}


@app.delete("/api/scripts/{name}")
@_guard
def delete_script(name: str):
    """删除脚本。"""
    path = script_model.script_path(name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"脚本 {name} 不存在")
    os.remove(path)
    return {"name": name, "deleted": True}


@app.post("/api/scripts/validate")
@_guard
def validate_script(payload: ScriptPayload):
    """校验脚本。"""
    script = script_model.from_dict(payload.script)
    return {"valid": True, "steps": len(script.steps)}


@app.get("/api/scripts/{name}/export")
@_guard
def export_script(name: str):
    """导出脚本内容（下载用）。"""
    return read_script(name)


@app.post("/api/scripts/import")
@_guard
def import_script(payload: ScriptPayload):
    """导入脚本。"""
    script = script_model.from_dict(payload.script)
    return {"name": script.name, "path": script_model.save(script)}


# ------------------------------------------------------------------ 运行


@app.post("/api/runs")
@_guard
def create_run(request: RunRequest):
    """创建并启动一次运行。"""
    script = script_model.resolve_script(request.script)
    target = _resolve(request.target_id)
    if not script.base_width or not script.base_height:
        script.base_width = target.width
        script.base_height = target.height
        script_model.save(script)
        logger.info(
            f"web.app.create_run: 脚本 {script.name!r} 未记录基准分辨率，"
            f"按目标 {target.id}（{target.name!r}）的实际尺寸记为 {target.width}x{target.height}"
        )
    executor = script_factory.create_runner(script, target)
    if request.from_step:
        executor.session.current_step_index = request.from_step - 2
    executor.start()
    _RUNNERS[executor.session.id] = executor
    return runner.session_to_dict(executor.session)


def _get_run(run_id: str):
    """
    按标识获取运行器。

    Args:
        run_id (str): 运行标识

    Returns:
        Runner: 运行器

    Raises:
        HTTPException: 运行标识不存在时抛出
    """
    executor = _RUNNERS.get(run_id)
    if executor is None:
        raise HTTPException(status_code=404, detail=f"运行会话 {run_id} 不存在")
    return executor


@app.get("/api/runs")
@_guard
def list_runs(target_id: Optional[str] = None):
    """列出历史运行记录，可按目标标识过滤。"""
    return runner.list_runs(target_id=target_id)


@app.get("/api/runs/{run_id}")
@_guard
def read_run(run_id: str):
    """读取运行会话详情。"""
    return runner.session_to_dict(_get_run(run_id).session)


@app.post("/api/runs/{run_id}/pause")
@_guard
def pause_run(run_id: str):
    """暂停运行。"""
    _get_run(run_id).pause()
    return runner.session_to_dict(_get_run(run_id).session)


@app.post("/api/runs/{run_id}/resume")
@_guard
def resume_run(run_id: str):
    """继续运行。"""
    _get_run(run_id).resume()
    return runner.session_to_dict(_get_run(run_id).session)


@app.post("/api/runs/{run_id}/stop")
@_guard
def stop_run(run_id: str):
    """停止运行。"""
    _get_run(run_id).stop("使用者在网页上点击停止")
    return runner.session_to_dict(_get_run(run_id).session)


@app.post("/api/runs/{run_id}/step")
@_guard
def step_run(run_id: str):
    """单步执行。"""
    return _get_run(run_id).step_once()


@app.post("/api/runs/{run_id}/retry-step")
@_guard
def retry_step(run_id: str):
    """重试当前步骤。"""
    return _get_run(run_id).retry_step()


@app.get("/api/runs/{run_id}/snapshots/{snapshot_id}.jpg")
@_guard
def read_snapshot(run_id: str, snapshot_id: str):
    """读取步骤画面快照。"""
    path = script_model.snapshot_file(run_id, snapshot_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"快照 {snapshot_id} 不存在")
    with open(path, "rb") as file:
        return Response(content=file.read(), media_type="image/jpeg")


@app.post("/api/runs/cleanup")
@_guard
def cleanup_runs():
    """按保留上限清理最旧的运行记录与快照。"""
    removed = runner.cleanup_runs()
    logger.info(f"web.app.cleanup_runs: 按保留上限清理运行记录，删除 {removed} 条")
    return {"removed": removed, "max_runs": script_model.max_runs()}


@app.get("/api/runs/{run_id}/events")
def _record_log(record) -> dict:
    """
    把执行记录转换为一行运行日志。

    Args:
        record (StepRecord): 执行记录

    Returns:
        dict: 含 message 的日志条目
    """
    suffix = f"，原因：{record.error}" if record.error else ""
    return {"message": f"步骤 {record.index}（{record.step_id}）{record.status}{suffix}"}


def run_events(run_id: str):
    """
    以 SSE 推送运行状态与逐步日志。

    步骤开始发 step_started、结束发 step_finished 与 step_<状态>，每条记录另发一条 log，
    循环末尾发 session_state。

    Args:
        run_id (str): 运行标识

    Returns:
        StreamingResponse: SSE 事件流
    """
    executor = _RUNNERS.get(run_id)
    if executor is None:
        raise HTTPException(status_code=404, detail=f"运行会话 {run_id} 不存在")

    def stream():
        sent = 0
        while True:
            session = executor.session
            records = session.records
            while sent < len(records):
                record = records[sent]
                sent += 1
                payload = json.dumps(runner._record_to_dict(record), ensure_ascii=False)
                if record.status == runner.STATUS_RUNNING:
                    yield f"event: step_started\ndata: {payload}\n\n"
                    continue
                yield f"event: step_{record.status}\ndata: {payload}\n\n"
                yield f"event: step_finished\ndata: {payload}\n\n"
                yield (f"event: log\n"
                       f"data: {json.dumps(_record_log(record), ensure_ascii=False)}\n\n")
            state_payload = json.dumps(
                {"state": session.state, "current_step_index": session.current_step_index},
                ensure_ascii=False,
            )
            yield f"event: session_state\ndata: {state_payload}\n\n"
            if executor.is_finished() and sent >= len(records):
                break
            time.sleep(0.3)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ------------------------------------------------------------------ 静态页面

ensure_dirs()
os.makedirs(scripts_dir(), exist_ok=True)
os.makedirs(runs_dir(), exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def serve(host: Optional[str] = None, port: Optional[int] = None) -> None:
    """
    启动网页服务。

    Args:
        host (str): 监听地址，None 时取配置（默认本机回环）
        port (int): 监听端口，None 时取配置
    """
    import uvicorn

    host = host or SETTINGS["web_host"]
    port = port or int(SETTINGS["web_port"])
    print(f"网页界面已启动，请在浏览器中打开 http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")
