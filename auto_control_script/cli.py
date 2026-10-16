# -*- coding: utf-8 -*-
"""
cli.py - 命令行入口模块

职责:
- 提供 targets / capture / ocr / input / run / cleanup / script 七个子命令
- 人类可读输出与 --json 机器可读输出两种形态
- 把异常按契约映射为稳定的退出码

调用链:
- __main__.py -> cli.py -> target.py / capture.py / ocr.py / interaction.py / runner.py

退出码:
- 0 成功；2 参数或脚本非法；3 目标不可用；4 执行失败；5 依赖缺失
"""

import argparse
import json
import logging
import sys
import time

from typing import Optional
from auto_control_script.capture import factory as capture
from auto_control_script.core import target as target_module
from auto_control_script.core.errors import (
    ActionError, AutoControlError, CaptureError, ChannelUnavailableError,
    DependencyMissingError, ScriptInvalidError, TargetUnavailableError,
)
from auto_control_script.core.frame import load as load_frame
from auto_control_script.core.settings import SETTINGS, ensure_dirs
from auto_control_script.core.target import Target
from auto_control_script.interaction import factory as interaction
from auto_control_script.interaction.base import ACTION_KINDS, Action
from auto_control_script.ocr import factory as ocr
from auto_control_script.script import factory as script_factory
from auto_control_script.script import model as script_model
from auto_control_script.script import runner

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_TARGET = 3
EXIT_FAILED = 4
EXIT_DEPENDENCY = 5

CODE_TO_EXIT = {
    "SCRIPT_INVALID": EXIT_INVALID,
    "TARGET_NOT_FOUND": EXIT_TARGET,
    "ACTION_FAILED": EXIT_FAILED,
    "TARGET_BUSY": EXIT_FAILED,
    "CAPTURE_FAILED": EXIT_FAILED,
    "CHANNEL_UNAVAILABLE": EXIT_DEPENDENCY,
    "DEPENDENCY_MISSING": EXIT_DEPENDENCY,
}

logger = logging.getLogger(__name__)


def _resolve(args) -> Target:
    """
    按命令行参数解析目标。

    Args:
        args: 含 target 属性的命令行参数对象

    Returns:
        Target: 目标对象
    """
    return target_module.resolve_target(args.target)


def _parse_region(text: str) -> tuple:
    """
    解析 "x1,y1,x2,y2" 形式的区域参数。

    Args:
        text (str): 区域字符串

    Returns:
        tuple: (x1, y1, x2, y2)

    Raises:
        ScriptInvalidError: 格式非法时抛出
    """
    parts = [item.strip() for item in (text or "").split(",")]
    if len(parts) != 4:
        raise ScriptInvalidError(
            f"cli._parse_region: 区域格式应为 x1,y1,x2,y2，实际收到 {text!r}"
        )
    return tuple(int(item) for item in parts)


def _parse_point(text: str) -> tuple:
    """
    解析 "x,y" 形式的坐标参数。

    Args:
        text (str): 坐标字符串

    Returns:
        tuple: (x, y)

    Raises:
        ScriptInvalidError: 格式非法时抛出
    """
    parts = [item.strip() for item in (text or "").split(",")]
    if len(parts) != 2:
        raise ScriptInvalidError(
            f"cli._parse_point: 坐标格式应为 x,y，实际收到 {text!r}"
        )
    return int(parts[0]), int(parts[1])


def cmd_targets(args) -> int:
    """
    列出可用目标。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    targets = target_module.list_targets(args.kind)
    rows = [{
        "kind": item.kind, "id": item.id, "name": item.name,
        "width": item.width, "height": item.height, "available": item.available,
        "visible": item.visible,
    } for item in targets]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        if not rows:
            print("没有找到可用目标")
        for row in rows:
            print(f"[{row['kind']}] {row['id']}  {row['name']}  "
                  f"{row['width']}x{row['height']}  available={row['available']}  "
                  f"visible={row['visible']}")
    return EXIT_OK


def cmd_capture(args) -> int:
    """
    截图并保存为图片文件。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    target = _resolve(args)
    region = _parse_region(args.region) if args.region else None
    frame = capture.save(target, args.out, region=region, path=args.path)
    if args.json:
        print(json.dumps({
            "file": args.out, "width": frame.width, "height": frame.height,
            "path": frame.path, "captured_at": frame.captured_at,
        }, ensure_ascii=False))
    else:
        print(f"已保存 {args.out}（{frame.width}x{frame.height}，取图路径={frame.path}）")
    return EXIT_OK


def cmd_ocr(args) -> int:
    """
    对目标画面或图片文件做 OCR。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    if args.image:
        frame = load_frame(args.image)
    else:
        target = _resolve(args)
        region = _parse_region(args.region) if args.region else None
        frame = (capture.capture_region(target, region, args.path) if region
                 else capture.capture(target, args.path))
    region = _parse_region(args.region) if (args.region and args.image) else None
    result = (ocr.recognize_region(frame, region, lang=args.lang, channel=args.channel)
              if region else ocr.recognize(frame, lang=args.lang, channel=args.channel))
    if args.json:
        print(json.dumps({
            "channel": result.channel, "channel_reason": result.channel_reason,
            "confidence_available": result.confidence_available, "language": result.language,
            "region": result.region,
            "items": [{
                "text": item.text, "box": item.box, "confidence": item.confidence,
                "order": item.order,
            } for item in result.items],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"通道={result.channel}（{result.channel_reason}），"
              f"置信度可用={result.confidence_available}，共 {len(result.items)} 条")
        for item in result.items:
            confidence = "无" if item.confidence is None else f"{item.confidence:.3f}"
            print(f"  [{item.order}] {item.text}  box={item.box}  conf={confidence}")
    return EXIT_OK


def cmd_input(args) -> int:
    """
    下发单次输入动作。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    target = _resolve(args)
    action = Action(
        kind=args.action,
        point=_parse_point(args.point) if args.point else None,
        end_point=_parse_point(args.end_point) if args.end_point else None,
        text=args.text,
        mode=args.mode,
        wait_before=args.wait_before,
        retry=args.retry,
    )
    interaction.perform(target, action)
    if args.json:
        print(json.dumps({"target": target.id, "action": action.kind, "mode": action.mode},
                         ensure_ascii=False))
    else:
        print(f"已在目标 {target.id}（{target.name}）上执行 {action.kind}（方式={action.mode}）")
    return EXIT_OK


def cmd_run(args) -> int:
    """
    运行脚本文件。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    script = script_model.resolve_script(args.script)
    target = _resolve(args)
    executor = script_factory.create_runner(script, target)
    if args.from_step:
        executor.session.current_step_index = args.from_step - 2
    executor.start()
    print(f"开始运行脚本 {script.name}（会话 {executor.session.id}）：")
    printed = 0
    while not executor.is_finished():
        while printed < len(executor.session.records):
            record = executor.session.records[printed]
            if record.status == runner.STATUS_RUNNING:
                break
            printed += 1
            line = (f"  [{record.index + 1}] {record.step_id} -> {record.status} "
                    f"({record.duration}s)")
            if record.error:
                line += f"  原因：{record.error}"
            print(line)
        time.sleep(0.2)
    while printed < len(executor.session.records):
        record = executor.session.records[printed]
        printed += 1
        print(f"  [{record.index + 1}] {record.step_id} -> {record.status} ({record.duration}s)")
    session_dict = runner.session_to_dict(executor.session)
    runner.cleanup_runs()
    if args.json:
        print(json.dumps(session_dict, ensure_ascii=False, indent=2))
    else:
        print(f"运行结束，状态={executor.session.state}，"
              f"成功 {sum(1 for item in executor.session.records if item.status == 'success')} 步，"
              f"失败 {sum(1 for item in executor.session.records if item.status == 'failed')} 步")
    return EXIT_OK if executor.session.state == runner.STATE_SUCCEEDED else EXIT_FAILED


def cmd_cleanup(args) -> int:
    """
    按保留上限清理最旧的运行记录与快照。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    removed = runner.cleanup_runs()
    if args.json:
        print(json.dumps({"removed": removed, "max_runs": script_model.max_runs()},
                         ensure_ascii=False, indent=2))
    else:
        print(f"清理完成：删除 {removed} 条运行记录（保留上限={script_model.max_runs()} 条）")
    return EXIT_OK


def cmd_script(args) -> int:
    """
    脚本管理：校验与查看概览。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    if args.script_action == "list":
        names = script_model.list_scripts()
        if args.json:
            print(json.dumps(names, ensure_ascii=False))
        else:
            print("\n".join(names) if names else "脚本目录为空")
        return EXIT_OK
    script = script_model.resolve_script(args.script)
    if args.script_action == "validate":
        errors = script_model.validate(script)
        if errors:
            print("\n".join(errors))
            return EXIT_INVALID
        print(f"脚本 {script.name} 校验通过（{len(script.steps)} 个步骤）")
        return EXIT_OK
    if args.script_action == "info":
        rows = [{"id": step.id, "type": step.type, "enabled": step.enabled,
                 "ref": step.ref, "on_fail": step.on_fail, "note": step.note}
                for step in script.steps]
        if args.json:
            print(json.dumps({
                "name": script.name, "version": script.version,
                "base_size": [script.base_width, script.base_height],
                "target_kind": script.target_kind, "steps": rows,
            }, ensure_ascii=False, indent=2))
        else:
            print(f"脚本 {script.name}（版本 {script.version}，"
                  f"基准分辨率 {script.base_width}x{script.base_height}）共 "
                  f"{len(rows)} 个步骤：")
            for row in rows:
                print(f"  {row['id']}  {row['type']}  enabled={row['enabled']}  "
                      f"ref={row['ref']}  失败策略={row['on_fail']}")
        return EXIT_OK
    raise ScriptInvalidError(
        f"cli.cmd_script: 未知脚本子命令 {args.script_action!r}，可选值为 "
        f"['validate', 'info', 'list']"
    )


def cmd_web(args) -> int:
    """
    启动网页界面服务。

    Args:
        args: 命令行参数对象

    Returns:
        int: 退出码
    """
    from auto_control_script.web.app import serve

    serve(host=args.host, port=args.port)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """
    构造命令行解析器。

    Returns:
        argparse.ArgumentParser: 解析器对象
    """
    parser = argparse.ArgumentParser(
        prog="python -m auto_control_script",
        description="统一截图·输入·OCR 自动化平台",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    common.add_argument("--verbose", action="store_true", help="输出详细日志")

    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_targets = subparsers.add_parser("targets", parents=[common], help="列出可用目标")
    p_targets.add_argument("--kind", default="all",
                           choices=["all", "window", "device", "desktop"], help="目标类型")
    p_targets.set_defaults(func=cmd_targets)

    p_capture = subparsers.add_parser("capture", parents=[common], help="截图并保存为文件")
    p_capture.add_argument("--target", required=True, help="目标标识或名称")
    p_capture.add_argument("--out", required=True, help="保存路径")
    p_capture.add_argument("--region", help="区域 x1,y1,x2,y2")
    p_capture.add_argument("--path", default=None,
                           choices=["auto", "printwindow", "bitblt", "wgc", "adb", "desktop"],
                           help="取图路径")
    p_capture.set_defaults(func=cmd_capture)

    p_ocr = subparsers.add_parser("ocr", parents=[common], help="识别画面或图片中的文字")
    p_ocr.add_argument("--target", help="目标标识或名称，与 --image 二选一")
    p_ocr.add_argument("--image", help="图片文件路径，与 --target 二选一")
    p_ocr.add_argument("--region", help="区域 x1,y1,x2,y2")
    p_ocr.add_argument("--lang", default=None, help="识别语言，如 ch / en")
    p_ocr.add_argument("--channel", default=None,
                       choices=["auto", "builtin", "precise"], help="OCR 通道")
    p_ocr.add_argument("--path", default=None,
                       choices=["auto", "printwindow", "bitblt", "wgc", "adb", "desktop"],
                       help="取图路径")
    p_ocr.set_defaults(func=cmd_ocr)

    p_input = subparsers.add_parser("input", parents=[common], help="下发单次输入动作")
    p_input.add_argument("--target", required=True, help="目标标识或名称")
    p_input.add_argument("--action", required=True,
                         choices=list(ACTION_KINDS), help="动作类型")
    p_input.add_argument("--point", help="坐标 x,y")
    p_input.add_argument("--end-point", help="拖拽终点 x,y")
    p_input.add_argument("--text", help="输入文本，或按键名/组合键/滚动量")
    p_input.add_argument("--mode", default=SETTINGS["input_mode"],
                         choices=["background", "foreground"], help="执行方式")
    p_input.add_argument("--wait-before", type=float, default=0.0, help="动作前等待秒数")
    p_input.add_argument("--retry", type=int, default=0, help="失败重试次数")
    p_input.set_defaults(func=cmd_input)

    p_run = subparsers.add_parser("run", parents=[common], help="运行脚本")
    p_run.add_argument("--script", required=True, help="脚本名或脚本文件路径")
    p_run.add_argument("--target", required=True, help="目标标识或名称")
    p_run.add_argument("--from-step", type=int, default=0, help="从第几步开始（1 起）")
    p_run.set_defaults(func=cmd_run)

    p_web = subparsers.add_parser("web", parents=[common], help="启动网页界面")
    p_web.add_argument("--host", default=None, help="监听地址，默认取配置（本机回环）")
    p_web.add_argument("--port", type=int, default=None, help="监听端口，默认取配置")
    p_web.set_defaults(func=cmd_web)

    p_cleanup = subparsers.add_parser("cleanup", parents=[common],
                                      help="按保留上限清理最旧的运行记录")
    p_cleanup.set_defaults(func=cmd_cleanup)

    p_script = subparsers.add_parser("script", parents=[common], help="脚本管理")
    p_script.add_argument("script_action", choices=["validate", "info", "list"],
                          help="操作：校验 / 查看概览 / 列出全部脚本")
    p_script.add_argument("--script", help="脚本名或脚本文件路径，list 时不需要")
    p_script.set_defaults(func=cmd_script)

    return parser


def main(argv: Optional[list] = None) -> int:
    """
    命令行入口。

    Args:
        argv (list): 命令行参数列表，None 时取 sys.argv[1:]

    Returns:
        int: 退出码
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    ensure_dirs()
    try:
        return args.func(args)
    except AutoControlError as error:
        print(f"错误（{error.code}）：{error}", file=sys.stderr)
        return CODE_TO_EXIT.get(error.code, EXIT_FAILED)
    finally:
        capture.release()
