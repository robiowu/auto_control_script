# -*- coding: utf-8 -*-
"""
tests/benchmark/ocr_benchmark.py - OCR 准确率与耗时基准

职责:
- 生成带真值标注的中文文字基准图，跑 OCR 并核对两条成功标准
  - SC-004：单条文本识别准确率不低于 90%，且包围盒中心落在文字区域内
  - SC-005：单次 OCR 区域识别耗时（首帧含模型加载，单独计量）

调用链:
- 人工执行 -> tests/benchmark/ocr_benchmark.py -> ocr/factory.py -> ocr/precise_ocr.py

运行方式：
    $env:PYTHONIOENCODING='utf-8'; conda run -n python313 python tests/benchmark/ocr_benchmark.py

口径：
- 基准图为合成渲染的清晰中文文字（微软雅黑），非真实界面截图；真实界面图由人工实机补测。
- 准确率取「精确匹配」为主口径，「包含匹配」为辅；两者均列出，不相互替代。
"""

import os
import sys
import time

import cv2
import numpy
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")
# 本脚本可直接执行，不依赖调用时的工作目录：先把项目根加入模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from auto_control_script.core.frame import Frame
from auto_control_script.ocr import factory as ocr

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
"""str: 基准图使用的中文字体路径。"""

BENCH_TEXTS = [
    "开始游戏", "设置", "确认", "取消", "背包", "商城", "任务", "排行榜", "好友", "邮件",
    "登录", "注册", "退出", "返回", "确定", "关闭", "购买", "出售", "装备", "技能",
    "角色", "地图", "聊天", "组队", "公会", "活动", "公告", "充值", "帮助", "音量",
]
"""list: 基准文本清单，取自界面常见中文词汇。"""

WARM_ROUNDS = 3
"""int: 热态耗时统计的重复轮数（首次加载单独计量，不计入）。"""

SC004_THRESHOLD = 0.9
"""float: SC-004 要求的单条文本识别准确率下限。"""


def render_benchmark_image(font_size: int = 32) -> tuple:
    """
    渲染中文文字基准图，并给出每条文本的真值包围盒。

    Args:
        font_size (int): 字号，默认 32

    Returns:
        tuple: (PIL 图像对象, {文本: 真值包围盒 (x1, y1, x2, y2)})
    """
    font = ImageFont.truetype(FONT_PATH, font_size)
    image = Image.new("RGB", (900, 60 * len(BENCH_TEXTS) + 60), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    truth = {}
    y = 30
    for text in BENCH_TEXTS:
        draw.text((40, y), text, font=font, fill=(0, 0, 0))
        truth[text] = draw.textbbox((40, y), text, font=font)
        y += 60
    return image, truth


def to_frame(image: Image.Image) -> Frame:
    """
    把 PIL 图像转换为画面帧。

    Args:
        image (Image.Image): RGB 顺序的 PIL 图像

    Returns:
        Frame: BGR 顺序的画面帧
    """
    bgr = cv2.cvtColor(numpy.array(image), cv2.COLOR_RGB2BGR)
    return Frame(pixels=bgr, width=image.width, height=image.height,
                 target_id="benchmark", path="benchmark")


def score(result, truth: dict) -> dict:
    """
    按真值比对识别结果，统计准确率与包围盒命中情况。

    Args:
        result: OCR 结果对象
        truth (dict): {文本: 真值包围盒}

    Returns:
        dict: 精确命中数、包含命中数、包围盒中心命中数与识别条数
    """
    exact = 0
    contained = 0
    inside = 0
    for text in BENCH_TEXTS:
        matched = [item for item in result.items if item.text == text]
        if matched:
            exact += 1
        if any(text in item.text for item in result.items):
            contained += 1
        for item in matched:
            box = truth[text]
            cx = (item.box[0] + item.box[2]) / 2
            cy = (item.box[1] + item.box[3]) / 2
            if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
                inside += 1
    return {"exact": exact, "contained": contained, "inside": inside,
            "total": len(BENCH_TEXTS), "recognized": len(result.items)}


def main() -> None:
    """
    执行基准并打印 SC-004 / SC-005 的实测结论。
    """
    image, truth = render_benchmark_image()
    frame = to_frame(image)

    start = time.perf_counter()
    first = ocr.recognize(frame)
    cold_elapsed = time.perf_counter() - start

    region = (0, 0, frame.width, min(600, frame.height))
    warm_full = []
    warm_region = []
    for _ in range(WARM_ROUNDS):
        start = time.perf_counter()
        ocr.recognize(frame)
        warm_full.append(time.perf_counter() - start)

        start = time.perf_counter()
        ocr.recognize_region(frame, region)
        warm_region.append(time.perf_counter() - start)

    stat = score(first, truth)
    exact_rate = stat["exact"] / stat["total"]
    contained_rate = stat["contained"] / stat["total"]

    print(f"通道={first.channel} 语言={first.language} "
          f"置信度可用={first.confidence_available}")
    print(f"SC-005 首帧耗时（含模型加载，不计入判定）={cold_elapsed:.3f}s")
    print(f"SC-005 热态整图平均={sum(warm_full) / len(warm_full):.3f}s "
          f"明细={[round(item, 3) for item in warm_full]}")
    print(f"SC-005 热态区域识别平均={sum(warm_region) / len(warm_region):.3f}s "
          f"明细={[round(item, 3) for item in warm_region]}")
    print(f"SC-004 精确匹配 {stat['exact']}/{stat['total']} = {exact_rate:.1%} "
          f"（阈值 {SC004_THRESHOLD:.0%}）")
    print(f"SC-004 包含匹配 {stat['contained']}/{stat['total']} = {contained_rate:.1%}")
    print(f"SC-004 包围盒中心落在文字区域内 {stat['inside']}/{stat['recognized']}")
    print(f"SC-004 判定：{'通过' if exact_rate >= SC004_THRESHOLD else '未通过'}")

    missed = [text for text in BENCH_TEXTS
              if not any(item.text == text for item in first.items)]
    if missed:
        print(f"未精确命中的文本：{missed}")


if __name__ == "__main__":
    main()
