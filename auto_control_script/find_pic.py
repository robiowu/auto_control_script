# -*- coding: utf-8 -*-
"""
find_pic.py - 窗口截图与图像识别模块

职责:
- 通过 Windows API 获取指定窗口的截图，转换为 numpy 数组
- 支持模板匹配（大图找小图），返回匹配位置和置信度
- 提供 FindPictureHelper 类封装截屏与资源管理

调用链:
- game_case.py -> find_pic.py -> cv2 / win32gui / win32ui / PIL / numpy
"""
import cv2
import win32gui
import win32ui
import win32con
import win32api
from PIL import Image
import numpy
import os


def get_cv2_numpy_image_from_file(filepath: str, cv2_imreadmodes: int = cv2.IMREAD_UNCHANGED):
    """
    将图片文件读入内存，返回 numpy 数组（RGB 格式）。

    Args:
        filepath (str): 图片路径，支持相对或绝对路径
        cv2_imreadmodes (int): OpenCV 读入模式，如 cv2.IMREAD_UNCHANGED

    Returns:
        numpy.ndarray | None: 等效的 numpy 对象，文件不存在则返回 None
    """
    result = None
    filepath = os.path.abspath(filepath)
    if os.path.isfile(filepath):
        result = cv2.imread(filepath, cv2_imreadmodes)
        result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    return result


def get_cv2_numpy_image_from_PyCBitmap(PyCBitmap_Object) -> numpy.ndarray:
    """
    将 PyCBitmap 对象转换为 numpy 数组（RGB 格式）。

    Args:
        PyCBitmap_Object: pywin32 的位图对象

    Returns:
        numpy.ndarray | None: 等效的 numpy 对象，失败返回 None
    """
    numpy_image = None
    try:
        bmpinfo = PyCBitmap_Object.GetInfo()
        bmp_array = numpy.frombuffer(PyCBitmap_Object.GetBitmapBits(True), dtype='uint8')
        pil_image = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                     bmp_array, 'raw', 'BGRX', 0, 1)
        numpy_image = numpy.array(pil_image)
    except Exception:
        pass
    return numpy_image


def find_sub_pic(source_image: numpy.ndarray, left: int, top: int, right: int, bottom: int,
                 template: numpy.ndarray, threshold: float = 0.9, is_gray: bool = True) -> tuple:
    """
    使用 OpenCV 模板匹配在大图中查找小图位置。

    Args:
        source_image (numpy.ndarray): 大图（源图像）
        left (int): 大图中查找区域的左坐标
        top (int): 大图中查找区域的上坐标
        right (int): 大图中查找区域的右坐标
        bottom (int): 大图中查找区域的下坐标
        template (numpy.ndarray): 要匹配的小图（模板）
        threshold (float): 匹配相似度阈值，范围 [-1, 1]，越接近 1 越严格
        is_gray (bool): 是否转为灰度图匹配（提升性能）

    Returns:
        tuple: (x, y, max_val) 最佳匹配的左上角坐标和置信度，未找到时返回 (-1, -1, max_val)
    """
    left = int(left)
    top = int(top)
    right = int(right)
    bottom = int(bottom)
    target = source_image[top:bottom, left:right]

    if is_gray:
        target_gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(target_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    else:
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    x = -1
    y = -1

    loc = numpy.where(result >= threshold)
    for point in zip(*loc[::-1]):
        x = max_loc[0]
        y = max_loc[1]
        break
    return x, y, max_val


class FindPictureHelper:
    """
    窗口截图与图像匹配辅助类。

    通过 Windows GDI 获取指定窗口的客户区截图，支持缩放和资源管理。
    """

    handle: int = None
    width: int = 0
    height: int = 0
    hwnd_DC = None
    mfc_DC = None
    save_DC = None
    save_bit_map = None
    numpy_image: numpy.ndarray = None
    dpi_multi: float = 1

    def __init__(self, winhandle: int, dpi_multi: float = 1):
        """
        初始化截图辅助类，获取窗口尺寸并创建 GDI 资源。

        Args:
            winhandle (int): 目标窗口句柄
            dpi_multi (float): DPI 缩放倍率，用于校正截图尺寸
        """
        self.dpi_multi = dpi_multi
        self.handle = winhandle
        left, top, right, bottom = win32gui.GetClientRect(winhandle)
        left, top = win32gui.ClientToScreen(winhandle, (left, top))
        right, bottom = win32gui.ClientToScreen(winhandle, (right, bottom))
        self.client_rect = (left, top, right, bottom)
        if (left, top, right, bottom) != win32gui.GetWindowRect(winhandle):
            temp = win32gui.GetWindowRect(winhandle)
            self.left_border = left - temp[0]
            self.top_border = top - temp[1]
            self.right_border = temp[2] - right
            self.bottom_border = temp[3] - bottom
        else:
            self.left_border = 0
            self.top_border = 0
            self.right_border = 0
            self.bottom_border = 0
        self.width = right - left
        self.height = bottom - top
        if self.dpi_multi != 1:
            self.width = int(self.width / self.dpi_multi)
            self.height = int(self.height / self.dpi_multi)
        self.hwnd_DC = win32gui.GetWindowDC(winhandle)
        self.mfc_DC = win32ui.CreateDCFromHandle(self.hwnd_DC)
        self.save_DC = self.mfc_DC.CreateCompatibleDC()
        self.save_bit_map = win32ui.CreateBitmap()
        self.save_bit_map.CreateCompatibleBitmap(self.mfc_DC, self.width, self.height)
        self.save_DC.SelectObject(self.save_bit_map)

    def get_window_image(self) -> None:
        """
        刷新窗口截图，将当前屏幕缓冲区复制到内存位图中。
        每次调用复用已分配的内存空间，不会产生内存泄漏。
        """
        self.save_DC.BitBlt((0, 0), (self.width, self.height),
                            self.mfc_DC, (self.left_border, self.top_border), win32con.SRCCOPY)
        self.numpy_image = get_cv2_numpy_image_from_PyCBitmap(PyCBitmap_Object=self.save_bit_map)

    def save_image(self, filepath: str, format: str = None) -> None:
        """
        保存当前窗口截图为图片文件。

        Args:
            filepath (str): 保存路径，含后缀名时自动识别格式
            format (str): 图片格式，如 "PNG"、"BMP"、"JPEG"，留空则根据后缀名自动识别
        """
        self.get_window_image()
        bmpinfo = self.save_bit_map.GetInfo()
        bmp_array = numpy.frombuffer(self.save_bit_map.GetBitmapBits(True), dtype=numpy.uint8)
        pil_image = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                     bmp_array, 'raw', 'BGRX', 0, 1)
        pil_image.save(filepath, format=format)

    def save_bmp(self, filepath: str = "zzx.bmp") -> None:
        """
        将当前内存位图保存为 BMP 文件。

        Args:
            filepath (str): 保存路径，若后缀非 .bmp 则自动追加
        """
        file_name = filepath
        if os.path.splitext(file_name)[-1] != "bmp":
            file_name = os.path.splitext(file_name)[0] + ".bmp"
        self.save_bit_map.SaveBitmapFile(self.save_DC, file_name)

    def release_resource(self) -> None:
        """释放 GDI 资源（位图句柄和设备上下文），避免内存泄漏。"""
        try:
            win32gui.DeleteObject(self.save_bit_map.GetHandle())
            self.save_DC.DeleteDC()
        except Exception:
            pass

    def find_sub_pic(self, sub_image_path: str, threshold: float = 0.9) -> tuple:
        """
        在已截取的全窗口中查找指定子图。

        Args:
            sub_image_path (str): 子图文件路径
            threshold (float): 匹配阈值 [-1, 1]，默认 0.9

        Returns:
            tuple: (x, y, threshold_real) 匹配位置和置信度，未找到时 x, y 为 -1
        """
        sub_image = get_cv2_numpy_image_from_file(sub_image_path)
        int_x, int_y, threshold_real = find_sub_pic(self.numpy_image, 0, 0,
                                                     self.width, self.height,
                                                     template=sub_image, threshold=threshold)
        return int_x, int_y, threshold_real


if __name__ == "__main__":
    a = numpy.arange(9.).reshape(3, 3)
    print(a)
    print(numpy.where(a > 9))
