# -*- coding: utf-8 -*-
"""
game_case.py - 自动化用例基类模块

职责:
- 提供 FeaturePic 特征图定义类（位置比例、点击区域、随机偏移、匹配参数）
- 提供 MyGameCase 基类：窗口定位、截图存档、特征查找、按字查找与点击输入

调用链:
- 具体用例脚本 -> game_case.py -> capture.py / matcher.py / interaction.py / ocr.py / logger.py

说明:
- 本轮重构后不再接受 dpi_multi 参数：DPI 换算由 window_manager 与 capture_win 自动完成
- 坐标一律使用图像坐标（相对客户区左上角的图像像素）
"""

import os

import cv2
from PIL import Image

from typing import Optional
from auto_control_script.capture import factory as capture
from auto_control_script.core import logger
from auto_control_script.core import target as target_module
from auto_control_script.core.frame import Frame, crop as crop_frame, load as load_frame
from auto_control_script.core.settings import SETTINGS, user_dir
from auto_control_script.core.window_manager import WindowManager
from auto_control_script.interaction import factory as interaction
from auto_control_script.interaction.base import (
    ACTION_CLICK, ACTION_DRAG, ACTION_INPUT_TEXT, ACTION_KEY, ACTION_SCROLL, Action,
)
from auto_control_script.matcher import factory as matcher


class FeaturePic:
    """
    特征图定义类。

    描述一张特征图在总图中的位置比例、点击区域比例和随机偏移量，
    用于自动化脚本中的图像识别与点击操作。
    """

    sizetuple: tuple   # (左倍率, 上倍率, 右倍率, 下倍率)
    path: str          # 特征图文件路径
    clicktuple: tuple  # (x倍率, y倍率) 点击点倍率
    randomtuple: tuple # (randomx倍率, randomy倍率)，None 时自动使用特征图大小
    msg: str           # 特征名称
    threshold: float = 0.95
    save_feature: Optional[str] = None
    is_gray: bool = True

    def __init__(self, sizetuple: tuple, path: str, clicktuple: tuple,
                 randomtuple: tuple, msg: str, **kwargs):
        """
        初始化特征图定义。

        Args:
            sizetuple (tuple): (l_multi, u_multi, r_multi, d_multi)
                特征图在总图中的左、上、右、下倍率
            path (str): 特征图文件路径，路径中不能包含中文
            clicktuple (tuple): (x_multi, y_multi) 需要点击的坐标在特征图中的倍率
            randomtuple (tuple): (randomx_multi, randomy_multi) 点击随机偏移倍率，
                None 则自动填充为特征图大小，(0, 0) 表示不做随机
            msg (str): 特征名称
            **kwargs: 扩展参数，支持 threshold、save_feature、is_gray
        """
        self.sizetuple = sizetuple
        self.path = path
        self.clicktuple = clicktuple
        self.randomtuple = randomtuple
        self.msg = msg
        if "threshold" in kwargs:
            self.threshold = kwargs["threshold"]
        if "save_feature" in kwargs:
            self.save_feature = kwargs["save_feature"]
        self.is_gray = bool(kwargs.get("is_gray", True))

    @staticmethod
    def get_sizetuple(source_image: str, feature_image: str, _round: int = 3) -> list:
        """
        计算小图在大图中的位置比例。

        Args:
            source_image (str): 大图文件路径
            feature_image (str): 小图（特征图）文件路径
            _round (int): 结果保留小数位数，默认 3

        Returns:
            list: [left_ratio, top_ratio, right_ratio, bottom_ratio]，
                未找到返回 None
        """
        source = load_frame(source_image)
        feature = load_frame(feature_image)
        result = matcher.find_by_image(source, feature.pixels,
                                       threshold=0.95, is_gray=False)
        if not result.found:
            return None
        left, top, right, bottom = result.box
        return [
            round(left / source.width, _round),
            round(top / source.height, _round),
            round(right / source.width, _round),
            round(bottom / source.height, _round),
        ]


class MyGameCase:
    """
    自动化用例基类。

    绑定一个 Windows 窗口，提供截图存档、特征查找、按字查找与各类输入动作，
    坐标一律使用图像坐标。
    """

    hwnd: int = 0
    game_name: str = "MyGameCase"

    def __init__(self, hwnd: int, game_name: str, base_size: dict, savelog: bool = False):
        """
        初始化用例基类。

        Args:
            hwnd (int): 窗口句柄
            game_name (str): 用例名称（用于日志目录命名）
            base_size (dict): 期望的客户区窗口尺寸，如 {"width": 540, "height": 960}
            savelog (bool): 是否保存日志到文件
        """
        self.hwnd = hwnd
        self.game_name = game_name
        self.base_size = base_size

        if not self.checkdir_char():
            raise RuntimeError(
                f"MyGameCase.__init__: 用例名称 {game_name!r} 含非法文件名字符，"
                f"不允许包含 \\ / : * ? \" < > |"
            )
        self._manager = WindowManager(hwnd)
        self.target = target_module.build_window_target(hwnd)
        self._log_dir = os.path.join(user_dir(), self.game_name)
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_helper = logger.Logger(
            filename=os.path.join(self._log_dir, f"{game_name}[{hwnd}].log"),
            backcount=3,
            savelog=savelog,
        )

    @property
    def log(self):
        """logging.Logger: 供子类调用 debug/info/warning/error 等方法。"""
        return self._log_helper.logger

    @property
    def width(self) -> int:
        """int: 当前客户区图像宽度。"""
        self._manager.refresh()
        return self._manager.pixel_width

    @property
    def height(self) -> int:
        """int: 当前客户区图像高度。"""
        self._manager.refresh()
        return self._manager.pixel_height

    def checkdir_char(self) -> bool:
        """
        检查用例名称是否包含非法文件名字符。

        Returns:
            bool: 合法返回 True，否则 False
        """
        if "" == self.game_name:
            return False
        for char in "\\/:*?\"<>|":
            if self.game_name.find(char) >= 0:
                return False
        return True

    def start_step(self, step_name: str) -> None:
        """输出步骤日志，自动递增步骤计数。"""
        if not hasattr(self.start_step, "step_count"):
            self.start_step.step_count = 1
        self.log.info(f"执行步骤{self.start_step.step_count}{step_name}")
        self.start_step.step_count += 1

    def capture_frame(self, region: Optional[tuple] = None, path: Optional[str] = None) -> Frame:
        """
        截取当前窗口画面。

        Args:
            region (tuple): 区域 (x1, y1, x2, y2)，None 表示整幅客户区
            path (str): 取图路径，None 时取配置默认值

        Returns:
            Frame: 画面帧
        """
        target_module.refresh(self.target)
        return (capture.capture_region(self.target, region, path) if region
                else capture.capture(self.target, path))

    def save_screenshot(self, name: str, region: Optional[tuple] = None) -> str:
        """
        截取画面并保存到用例日志目录。

        Args:
            name (str): 保存文件名（含扩展名）
            region (tuple): 区域，None 表示整幅客户区

        Returns:
            str: 保存后的文件绝对路径
        """
        filepath = os.path.join(self._log_dir, name)
        capture.save(self.target, filepath, region=region)
        return filepath

    def find_feature(self, sub_image_path: str, subsize_tuple: Optional[tuple] = None,
                     save_feature: Optional[str] = None, threshold: float = 0.95,
                     is_gray: bool = True) -> tuple:
        """
        在窗口截图中查找指定子图。

        Args:
            sub_image_path (str): 子图文件路径
            subsize_tuple (tuple): (左, 上, 右, 下) 倍率，原图为 (0, 0, 1, 1)
            save_feature (str): 非 None 时保存挖块特征图到该路径
            threshold (float): 匹配相似度阈值
            is_gray (bool): 是否使用灰度图匹配

        Returns:
            tuple: (x, y, threshold_real) 匹配位置与置信度；未找到时 x 与 y 均为 -1
        """
        subsize_tuple = subsize_tuple or (0, 0, 1, 1)
        if any(item > 1 or item < 0 for item in subsize_tuple):
            subsize_tuple = (0, 0, 1, 1)

        frame = self.capture_frame()
        width = self.base_size["width"]
        height = self.base_size["height"]
        resized_pixels = cv2.resize(frame.pixels, (width, height))
        resized = Frame(pixels=resized_pixels, width=width, height=height,
                        target_id=frame.target_id, path=frame.path)
        subsize = (
            int(subsize_tuple[0] * width), int(subsize_tuple[1] * height),
            int(subsize_tuple[2] * width), int(subsize_tuple[3] * height),
        )
        sub_image = load_frame(sub_image_path).pixels
        if sub_image.shape[0] == height and sub_image.shape[1] == width:
            sub_image = sub_image[subsize[1]:subsize[3], subsize[0]:subsize[2]]
            if save_feature:
                Image.fromarray(sub_image).save(save_feature)
                Image.fromarray(
                    resized_pixels[subsize[1]:subsize[3], subsize[0]:subsize[2]]
                ).save(f"{save_feature}.main.bmp")

        result = matcher.find_by_image(
            crop_frame(resized, subsize), sub_image, threshold=threshold, is_gray=is_gray)
        if not result.found:
            return -1, -1, result.score
        x, y = result.box[0], result.box[1]
        return x + subsize[0], y + subsize[1], result.score

    def check_feature(self, feature: FeaturePic) -> dict:
        """
        检测特征图是否存在，并计算点击坐标。

        Args:
            feature (FeaturePic): 特征图定义对象

        Returns:
            dict: 含 result、intx、inty、threshold、point_x、point_y、random_x、random_y
        """
        intx, inty, threshold_val = self.find_feature(
            sub_image_path=feature.path, subsize_tuple=feature.sizetuple,
            save_feature=feature.save_feature, threshold=feature.threshold,
            is_gray=feature.is_gray,
        )
        point_x = intx if not feature.clicktuple else int(feature.clicktuple[0] * self.width)
        point_y = inty if not feature.clicktuple else int(feature.clicktuple[1] * self.height)
        if not feature.randomtuple:
            random_x = int((feature.sizetuple[2] - feature.sizetuple[0]) * self.width)
            random_y = int((feature.sizetuple[3] - feature.sizetuple[1]) * self.height)
        else:
            random_x = int(feature.randomtuple[0] * self.width)
            random_y = int(feature.randomtuple[1] * self.height)
        return {
            "result": intx >= 0 and inty >= 0,
            "intx": intx, "inty": inty, "threshold": threshold_val,
            "point_x": point_x, "point_y": point_y,
            "random_x": random_x, "random_y": random_y,
        }

    def click(self, x: int, y: int, mode: Optional[str] = None) -> None:
        """
        在指定坐标点击。

        Args:
            x (int): 图像横坐标
            y (int): 图像纵坐标
            mode (str): 执行方式，None 时取配置默认值
        """
        interaction.perform(self.target, Action(
            kind=ACTION_CLICK, point=(x, y),
            mode=mode or SETTINGS["input_mode"]))

    def click_feature(self, feature: FeaturePic) -> bool:
        """
        查找特征图并点击。

        Args:
            feature (FeaturePic): 特征图定义对象

        Returns:
            bool: 命中并点击返回 True，未命中返回 False
        """
        info = self.check_feature(feature)
        if not info["result"]:
            self.log.warning(f"未找到特征图 {feature.msg}（{feature.path}）")
            return False
        self.click(info["point_x"], info["point_y"])
        return True

    def find_word(self, word: str, region: Optional[tuple] = None, lang: Optional[str] = None,
                  channel: Optional[str] = None) -> tuple:
        """
        查找文字位置。

        Args:
            word (str): 目标文字
            region (tuple): 查找区域，None 表示整幅画面
            lang (str): 识别语言
            channel (str): OCR 通道

        Returns:
            tuple: (x, y) 文字中心坐标；未找到时返回 (-1, -1)
        """
        frame = self.capture_frame()
        result = matcher.find_by_text(frame, word, lang=lang, channel=channel, region=region)
        if not result.found:
            return -1, -1
        return result.point

    def click_word(self, word: str, region: Optional[tuple] = None, mode: Optional[str] = None) -> bool:
        """
        查找文字并点击。

        Args:
            word (str): 目标文字
            region (tuple): 查找区域
            mode (str): 执行方式

        Returns:
            bool: 命中并点击返回 True，未命中返回 False
        """
        point = self.find_word(word, region=region)
        if point == (-1, -1):
            self.log.warning(f"未找到文字 {word}")
            return False
        self.click(point[0], point[1], mode=mode)
        return True

    def input_text(self, text: str, mode: Optional[str] = None) -> None:
        """
        输入文本。

        Args:
            text (str): 待输入文本
            mode (str): 执行方式
        """
        interaction.perform(self.target, Action(
            kind=ACTION_INPUT_TEXT, text=text,
            mode=mode or SETTINGS["input_mode"]))

    def press_key(self, key: str, mode: Optional[str] = None) -> None:
        """
        按下按键。

        Args:
            key (str): 按键名或单字符
            mode (str): 执行方式
        """
        interaction.perform(self.target, Action(
            kind=ACTION_KEY, text=key,
            mode=mode or SETTINGS["input_mode"]))

    def scroll(self, amount: int, x: int, y: int, mode: Optional[str] = None) -> None:
        """
        在指定位置滚动滚轮。

        Args:
            amount (int): 滚动量，正数向上、负数向下
            x (int): 图像横坐标
            y (int): 图像纵坐标
            mode (str): 执行方式
        """
        interaction.perform(self.target, Action(
            kind=ACTION_SCROLL, point=(x, y), text=str(amount),
            mode=mode or SETTINGS["input_mode"]))

    def drag(self, start: tuple, end: tuple, mode: Optional[str] = None) -> None:
        """
        从起点拖拽到终点。

        Args:
            start (tuple): 起点 (x, y)
            end (tuple): 终点 (x, y)
            mode (str): 执行方式
        """
        interaction.perform(self.target, Action(
            kind=ACTION_DRAG, point=tuple(start), end_point=tuple(end),
            mode=mode or SETTINGS["input_mode"]))

    def finish_log(self) -> None:
        """输出用例结束日志。"""
        self.log.info(f"用例 {self.game_name} 执行结束")
