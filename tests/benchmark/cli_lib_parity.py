# -*- coding: utf-8 -*-
"""
tests/benchmark/cli_lib_parity.py - 命令行与库调用的语义一致性核对

职责:
- 对同一张图片与同一区域，分别走 CLI 与库调用，核对返回语义一致（SC-006）
- 对同一错误场景（图片文件不存在），核对两侧报出的错误码一致

调用链:
- 人工执行 -> cli_lib_parity.py -> 子进程 `python -m auto_control_script ocr`
                                -> ocr/factory.py

运行方式：
    $env:PYTHONIOENCODING='utf-8'; conda run -n python313 python tests/benchmark/cli_lib_parity.py

口径：
- 「语义一致」指同一输入下，通道标识、置信度可用性、识别条数、每条文本/包围盒/顺序完全一致。
- 错误侧只比对错误码（CLI 退出码由 CODE_TO_EXIT 从错误码映射而来，故比对错误码即可）。
"""

import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")
# 本脚本可直接执行，不依赖调用时的工作目录：先把项目根加入模块搜索路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from auto_control_script.core.errors import CaptureError
from auto_control_script.core.frame import load as load_frame
from auto_control_script.ocr import factory as ocr

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
"""str: 基准图使用的中文字体路径。"""

TEXTS = ["开始游戏", "背包", "排行榜", "设置", "确认"]
"""list: 基准图上的文本。"""

REGION = (0, 0, 400, 220)
"""tuple: 区域识别比对使用的区域 (x1, y1, x2, y2)。"""

_missing_image = os.path.join(tempfile.gettempdir(), "_parity_不存在的图.png")
"""str: 错误场景使用的不存在的图片路径。"""


def render_image(path: str) -> None:
    """
    渲染一张中文文字图并保存到指定路径。

    Args:
        path (str): 图片保存路径
    """
    font = ImageFont.truetype(FONT_PATH, 32)
    image = Image.new("RGB", (900, 400), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    y = 30
    for text in TEXTS:
        draw.text((40, y), text, font=font, fill=(0, 0, 0))
        y += 60
    image.save(path)


def run_cli(*extra: str) -> tuple:
    """
    以子进程方式调用命令行。

    Args:
        *extra (str): 追加给子命令的参数

    Returns:
        tuple: (退出码, stdout, stderr)
    """
    process = subprocess.run(
        [sys.executable, "-m", "auto_control_script", "ocr", *extra],
        capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT,
    )
    return process.returncode, process.stdout, process.stderr


def compare(label: str, cli_value, lib_value) -> bool:
    """
    比对一项并打印结果。

    Args:
        label (str): 比对项名称
        cli_value: 命令行侧取值
        lib_value: 库调用侧取值

    Returns:
        bool: 两侧一致为 True
    """
    ok = cli_value == lib_value
    print(f"{'一致' if ok else '不一致'}  {label}: CLI={cli_value!r} 库={lib_value!r}")
    return ok


def compare_items(label: str, cli_items: list, lib_items: list) -> bool:
    """
    逐条比对识别结果。

    Args:
        label (str): 场景名称
        cli_items (list): 命令行返回的条目列表
        lib_items (list): 库调用返回的条目列表

    Returns:
        bool: 全部一致为 True
    """
    ok = compare(f"{label} 识别条数", len(cli_items), len(lib_items))
    for index, (cli_item, lib_item) in enumerate(zip(cli_items, lib_items)):
        ok = compare(f"{label} items[{index}].text", cli_item["text"], lib_item.text) and ok
        ok = compare(f"{label} items[{index}].box",
                     tuple(cli_item["box"]), tuple(lib_item.box)) and ok
        ok = compare(f"{label} items[{index}].order", cli_item["order"], lib_item.order) and ok
    return ok


def main() -> None:
    """
    执行 CLI 与库调用的一致性核对并打印 SC-006 结论。
    """
    with tempfile.TemporaryDirectory() as directory:
        image_path = os.path.join(directory, "parity.png")
        render_image(image_path)

        region_text = ",".join(str(value) for value in REGION)

        code, stdout, stderr = run_cli("--image", image_path, "--json")
        cli_full = json.loads(stdout)
        lib_full = ocr.recognize(load_frame(image_path))

        print("=== 整图识别 ===")
        ok = compare("退出码", code, 0)
        ok = compare("channel", cli_full["channel"], lib_full.channel) and ok
        ok = compare("confidence_available",
                     cli_full["confidence_available"], lib_full.confidence_available) and ok
        ok = compare_items("整图", cli_full["items"], lib_full.items) and ok

        code, stdout, stderr = run_cli("--image", image_path, "--region", region_text, "--json")
        cli_region = json.loads(stdout)
        lib_region = ocr.recognize_region(load_frame(image_path), REGION)

        print("=== 区域识别 ===")
        ok = compare("退出码", code, 0) and ok
        ok = compare("region 回写", tuple(cli_region["region"]), tuple(lib_region.region)) and ok
        ok = compare_items("区域", cli_region["items"], lib_region.items) and ok

    print("=== 错误场景：图片不存在 ===")
    code, stdout, stderr = run_cli("--image", _missing_image, "--json")
    cli_error_code = stderr.split("（")[1].split("）")[0] if "（" in stderr else None
    try:
        load_frame(_missing_image)
        lib_error_code = None
    except CaptureError as error:
        lib_error_code = error.code
    ok = compare("错误码", cli_error_code, lib_error_code) and ok
    ok = compare("退出码非 0", code != 0, True) and ok

    print(f"SC-006 判定：{'通过' if ok else '未通过'}")


if __name__ == "__main__":
    main()
