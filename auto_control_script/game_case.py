# -*- coding: utf-8 -*-
"""
game_case.py - 游戏自动化脚本基类模块

职责:
- 提供 FeaturePic 特征图定义类（位置、点击区域、随机偏移、匹配参数）
- 提供 MyGameCase 游戏脚本基类（窗口管理、日志、特征查找、特征点击）

调用链:
- 游戏具体脚本 -> game_case.py -> find_pic / win_handle / my_log / system_cmd
"""
import os
import cv2
from PIL import Image
import auto_control_script.my_log as my_log
import auto_control_script.find_pic as find_pic
import auto_control_script.system_cmd as system_cmd
from auto_control_script.win_handle import Window


class FeaturePic:
    """
    特征图定义类。

    描述一张特征图在总图中的位置比例、点击区域比例和随机偏移量，
    用于自动化脚本中的图像识别与点击操作。
    """

    sizetuple: tuple  # (左倍率, 上倍率, 右倍率, 下倍率)
    path: str         # 特征图文件路径
    clicktuple: tuple  # (x倍率, y倍率) 点击点倍率
    randomtuple: tuple  # (randomx倍率, randomy倍率)，None 时自动使用特征图大小
    msg: str           # 特征名称
    threshold: float = 0.95
    save_feature: str = None
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
        if "is_gray" in kwargs:
            self.is_gray = kwargs["is_gray"]
        else:
            self.is_gray = True

    @staticmethod
    def get_sizetuple(source_image: str, feature_image: str, _round: int = 3) -> list:
        """
        计算小图在大图中的位置比例。

        Args:
            source_image (str): 大图文件路径
            feature_image (str): 小图（特征图）文件路径
            _round (int): 结果保留小数位数，默认 3

        Returns:
            list | None: [left_ratio, top_ratio, right_ratio, bottom_ratio]
                找到时返回比例列表，未找到返回 None
        """
        result = None
        source_image = find_pic.get_cv2_numpy_image_from_file(source_image)
        feature_image = find_pic.get_cv2_numpy_image_from_file(feature_image)

        height, width, channels = source_image.shape
        sub_height, sub_width, sub_channels = feature_image.shape

        left, up, _ = find_pic.find_sub_pic(
            source_image=source_image, template=feature_image,
            left=0, top=0, right=width, bottom=height, is_gray=False)
        if left > 0:
            result = []
            result.append(round(left / width, _round))
            result.append(round(up / height, _round))
            result.append(round((left + sub_width) / width, _round))
            result.append(round((up + sub_height) / height, _round))
        return result


class MyGameCase:
    """游戏自动化脚本基类，提供窗口管理、截图匹配、日志等功能。"""

    hwnd: int = 0
    window: Window = None
    find_pic_helper: find_pic.FindPictureHelper = None
    game_name: str = "MyGameCase"

    _log_helper = None
    _log_dir: str = None
    _log_name: str = None

    def __init__(self, hwnd: int, game_name: str, base_size: dict,
                 dpi_multi: float = 1, savelog: bool = False):
        """
        初始化游戏脚本基类。

        Args:
            hwnd (int): 窗口句柄
            game_name (str): 游戏名称（用于日志目录命名）
            base_size (dict): 期望的客户区窗口尺寸，如 {"width": 540, "height": 960}
            dpi_multi (float): DPI 缩放倍率，默认 1
            savelog (bool): 是否保存日志到文件
        """
        self.hwnd = hwnd
        self.dpi_multi = dpi_multi
        self.window = Window(self.hwnd)
        self.find_pic_helper = find_pic.FindPictureHelper(self.hwnd, dpi_multi=dpi_multi)
        self.game_name = game_name
        self.base_size = base_size

        assert self.checkdir_char()
        self._log_dir = os.path.join(system_cmd.get_abs_appdata_path(), "auto_control_script", self.game_name)
        self._log_name = f"{game_name}[{hwnd}].log"
        if not os.path.exists(self._log_dir):
            os.makedirs(self._log_dir)
        self._log_init(self._log_dir, self._log_name, savelog)

    def _log_init(self, log_abs_filepath: str, log_filename: str, savelog: bool) -> None:
        """
        初始化日志模块。

        Args:
            log_abs_filepath (str): 日志保存目录的绝对路径
            log_filename (str): 日志文件名
            savelog (bool): 是否保存日志到文件
        """
        filename = os.path.join(log_abs_filepath, log_filename)
        self._log_helper = my_log.Logger(filename=filename, backcount=3, savelog=savelog)

    def checkdir_char(self) -> bool:
        """
        检查游戏名称是否包含非法文件名字符。

        Returns:
            bool: 合法返回 True，否则 False
        """
        if "" == self.game_name:
            return False
        forbid = "\\/:*?\"<>|"
        for char in forbid:
            if self.game_name.find(char) >= 0:
                return False
        return True

    def start_step(self, step_name: str) -> None:
        """输出步骤日志，自动递增步骤计数。"""
        if not hasattr(self.start_step, "step_count"):
            self.start_step.step_count = 1
        self.log.info(f"执行步骤{self.start_step.step_count}{step_name}")

    @property
    def log(self):
        """获取 Logger 实例，供子类调用 debug/info/warning/error 等方法。"""
        return self._log_helper.logger

    def save_log(self, info: str) -> None:
        """（预留接口）保存自定义日志信息。"""
        pass

    def find_feature(self, sub_image_path: str, subsize_tuple: tuple = None,
                     save_feature: str = None, threshold: float = 0.95,
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
            tuple: (x, y, threshold_real) 匹配位置和置信度
        """
        if not subsize_tuple:
            subsize_tuple = (0, 0, 1, 1)
        for i in subsize_tuple:
            if i > 1 or i < 0:
                subsize_tuple = (0, 0, 1, 1)
                break
        self.find_pic_helper.get_window_image()
        resized = cv2.resize(self.find_pic_helper.numpy_image,
                             (self.base_size["width"], self.base_size["height"]))
        subsize = (
            int(subsize_tuple[0] * self.base_size["width"]),
            int(subsize_tuple[1] * self.base_size["height"]),
            int(subsize_tuple[2] * self.base_size["width"]),
            int(subsize_tuple[3] * self.base_size["height"]),
        )
        sub_image = find_pic.get_cv2_numpy_image_from_file(sub_image_path)
        if sub_image.shape[0] == self.base_size["height"] and sub_image.shape[1] == self.base_size["width"]:
            sub_image = sub_image[subsize[1]:subsize[3], subsize[0]:subsize[2]]
            if save_feature:
                im = Image.fromarray(sub_image)
                im.save(save_feature)
                im = Image.fromarray(resized[subsize[1]:subsize[3], subsize[0]:subsize[2]])
                im.save(f"{save_feature}.main.bmp")
        int_x, int_y, threshold_real = find_pic.find_sub_pic(
            resized, *subsize, template=sub_image, threshold=threshold, is_gray=is_gray)
        if int_x >= 0:
            int_x += int(subsize_tuple[0] * self.base_size["width"])
        if int_y >= 0:
            int_y += int(subsize_tuple[1] * self.base_size["height"])
        return int_x, int_y, threshold_real

    def check_feature(self, feature: FeaturePic) -> dict:
        """
        检测特征图是否存在，并计算点击坐标。

        Args:
            feature (FeaturePic): 特征图定义对象

        Returns:
            dict: 包含 result、intx、inty、threshold、point_x、point_y、random_x、random_y
        """
        threshold = feature.__dict__.get("threshold", 0.95)
        save_feature = feature.__dict__.get("save_feature")
        is_gray = feature.__dict__.get("is_gray", True)
        intx, inty, threshold_val = self.find_feature(
            sub_image_path=feature.path, subsize_tuple=feature.sizetuple,
            save_feature=save_feature, threshold=threshold, is_gray=is_gray,
        )
        if not feature.clicktuple:
            point_x = intx
            point_y = inty
        else:
            point_x = int(feature.clicktuple[0] * self.find_pic_helper.width)
            point_y = int(feature.clicktuple[1] * self.find_pic_helper.height)
        if not feature.randomtuple:
            random_x = int((feature.sizetuple[2] - feature.sizetuple[0]) * self.find_pic_helper.width)
            random_y = int((feature.sizetuple[3] - feature.sizetuple[1]) * self.find_pic_helper.height)
        else:
            random_x = int(feature.randomtuple[0] * self.find_pic_helper.width)
            random_y = int(feature.randomtuple[1] * self.find_pic_helper.height)
        result = {
            "intx": intx, "inty": inty, "threshold": threshold_val,
            "point_x": point_x, "point_y": point_y,
            "random_x": random_x, "random_y": random_y,
        }
        if intx >= 0 and inty >= 0:
            result["result"] = True
            return result
        result["result"] = False
        return result
