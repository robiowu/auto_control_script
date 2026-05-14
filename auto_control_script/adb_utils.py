# -*- coding: utf-8 -*-
"""
adb_utils.py - ADB 设备控制模块

职责:
- 通过 ADB 协议管理 Android 设备连接
- 提供设备截图、点击、滑动操作
- 提供应用生命周期管理（启停、状态检测）

调用链:
- game_case.py -> adb_utils.py -> adb / subprocess / cv2 / PIL
"""
import io
import os
import datetime
import subprocess
import numpy
import cv2
from PIL import Image


class AdbUtils:
    """Android ADB 设备控制工具类"""

    adb: str = "adb"
    device_id: str = None
    app_name: str = None
    activity_name: str = None

    def __init__(self, dev_id: str, use_adb: bool = True,
                 app_name: str = None, activity_name: str = None):
        """
        初始化 ADB 工具，连接设备。

        Args:
            dev_id (str): 设备 ID（USB 连接时）或 IP:port（无线连接时）
            use_adb (bool): 是否使用 adb 命令，默认 True
            app_name (str): 要控制的应用包名
            activity_name (str): 应用启动 Activity 名
        """
        if use_adb:
            self.adb = "adb"
        self.device_id = dev_id
        self._connect_device()
        self.app_name = app_name
        self.activity_name = activity_name

    def print(self, string: str, timestamp: bool = True) -> None:
        """
        打印日志，若存在 logger 属性则使用 logger，否则使用标准输出。

        Args:
            string (str): 要输出的字符串
            timestamp (bool): 是否添加时间戳前缀
        """
        logger = getattr(self, 'logger', None)
        if logger is not None:
            logger.info(string)
        else:
            if timestamp:
                now = datetime.datetime.now()
                timestamp_prefix = now.strftime("%m-%d %H:%M:%S")
                string = f"[{timestamp_prefix}] {string}"
            print(string)

    def _connect_device(self) -> tuple:
        """连接 ADB 设备，根据 device_id 格式自动选择 USB 或无线连接模式。"""
        if self.device_id.find(":") < 0:
            command = f"{self.adb} devices"
        else:
            command = f"{self.adb} connect {self.device_id}"
        self.print(command)
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout, result.stderr
        except subprocess.SubprocessError as e:
            return None, str(e)

    def launch_app(self) -> tuple:
        """
        通过 ADB 启动指定应用。

        Returns:
            tuple: (stdout, stderr) 或异常时 (None, error_msg)
        """
        command = (f"{self.adb} -s {self.device_id} "
                   f"shell am start -n "
                   f"{self.app_name}/{self.activity_name}")
        self.print(command)
        try:
            result = self.subprocess_run_print(command)
            return result.stdout, result.stderr
        except subprocess.SubprocessError as e:
            return None, str(e)

    def kill_app(self) -> tuple:
        """
        通过 ADB 强制停止指定应用。

        Returns:
            tuple: (success, message) success 为 bool
        """
        command = f"{self.adb} -s {self.device_id} shell am force-stop {self.app_name}"
        self.print(command)
        try:
            result = self.subprocess_run_print(command)
            if result.stderr:
                return False, result.stderr
            return True, "Process killed successfully."
        except subprocess.SubprocessError as e:
            return False, str(e)

    def get_physical_size(self) -> tuple:
        """
        获取设备物理屏幕分辨率。

        Returns:
            tuple: (width, height) 或 None（解析失败时）
        """
        wm_size = f"{self.adb} -s {self.device_id} shell wm size"
        wm_size = subprocess.run(wm_size, capture_output=True, text=True, shell=True)
        wm_size = wm_size.stdout
        lines = wm_size.split("\n")
        for line in lines:
            if "Physical size:" in line:
                temp = line.replace("Physical size: ", "").strip()
                width, height = temp.split("x")
                return int(width), int(height)
        return None

    def subprocess_run_print(self, command: str, std_out: bool = True,
                             std_err: bool = True) -> subprocess.CompletedProcess:
        """
        执行 shell 命令并打印输出。

        Args:
            command (str): 要执行的命令
            std_out (bool): 是否打印标准输出
            std_err (bool): 是否打印标准错误

        Returns:
            subprocess.CompletedProcess: 命令执行结果
        """
        self.print(command)
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if std_out and result.stdout:
            self.print(result.stdout.rstrip())
        if std_err and result.stderr:
            self.print(result.stderr.rstrip())
        return result

    def get_game_status(self) -> bool:
        """
        检查应用是否正在运行。

        Returns:
            bool: 运行中返回 True，否则 False
        """
        cmd = f'{self.adb} -s {self.device_id} shell "ps | grep {self.app_name}"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout or result.returncode == 0:
                self.print("游戏正在运行")
                return True
            else:
                self.print("游戏已关闭")
                return False
        except subprocess.SubprocessError as e:
            self.print(f"游戏状态异常：{str(e)}")
            return False

    def init_game(self) -> None:
        """检查游戏状态，若未运行则启动。"""
        if not self.get_game_status():
            self.launch_app()

    def get_image(self) -> Image.Image:
        """
        通过 ADB screencap 获取设备屏幕截图。

        Returns:
            PIL.Image.Image: 设备屏幕的 PIL 图像对象
        """
        screencap_cmd = f"{self.adb} -s {self.device_id} shell screencap -p"
        proc = subprocess.Popen(screencap_cmd, stdout=subprocess.PIPE, shell=True)
        image_bytes = proc.stdout.read()
        if os.name == 'nt':
            image_bytes = image_bytes.replace(b'\r\n', b'\n')
        image = Image.open(io.BytesIO(image_bytes))
        return image

    def get_opencv_image(self) -> numpy.ndarray:
        """
        获取设备屏幕截图的 OpenCV 格式（RGB numpy 数组）。

        Returns:
            numpy.ndarray: RGB 格式的屏幕图像数组
        """
        image = numpy.array(self.get_image())
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        return image

    def save_image(self, filepath: str) -> Image.Image:
        """
        将设备屏幕截图保存到文件。

        Args:
            filepath (str): 保存路径

        Returns:
            PIL.Image.Image: 保存的图像对象
        """
        image = self.get_image()
        image.save(filepath)
        return image

    def click(self, x: int, y: int) -> tuple:
        """
        在设备屏幕上模拟点击。

        Args:
            x (int): 点击 X 坐标
            y (int): 点击 Y 坐标

        Returns:
            tuple: (x, y) 实际点击坐标
        """
        cmd = f"{self.adb} -s {self.device_id} shell input tap {int(x)} {int(y)}"
        self.subprocess_run_print(command=cmd)
        return x, y

    def scroll(self, x_begin: int, y_begin: int, x_end: int, y_end: int) -> None:
        """
        在设备屏幕上模拟滑动。

        Args:
            x_begin (int): 起始 X 坐标
            y_begin (int): 起始 Y 坐标
            x_end (int): 结束 X 坐标
            y_end (int): 结束 Y 坐标
        """
        os.system(f"{self.adb} -s {self.device_id} shell input swipe "
                  f"{x_begin} {y_begin} {x_end} {y_end} 300")


if __name__ == "__main__":
    ip = "127.0.0.1"
    port = "16448"
    a = AdbUtils(f"{ip}:{port}")
    w, h = a.get_physical_size()
    print(f"{w} : {h}")
