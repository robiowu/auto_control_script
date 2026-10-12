# -*- coding: utf-8 -*-
"""
capture/window_capture.py - Windows 窗口截图模块

职责:
- 提供三条取图路径：PrintWindow(PW_RENDERFULLCONTENT)、BitBlt、WGC 后台会话
- 统一裁剪为客户区并完成缩放换算，使图像坐标可直接下发给点击动作
- 提供资源释放入口

调用链:
- capture.py -> capture_win.py -> window_manager.py / frame.py / win32gui / win32ui / windows_capture

说明:
- auto 模式会按 printwindow -> wgc（已安装时）-> bitblt 的顺序尝试，
  每次切换都记录原因；显式指定路径时只尝试该路径，失败即报错不回退
"""

import ctypes
import logging
import threading
import time

import numpy
import win32con
import win32gui
import win32ui

from typing import Optional
from auto_control_script.capture.base import PATH_AUTO, BaseCapture
from auto_control_script.core import frame as frame_module
from auto_control_script.core.errors import CaptureError, ChannelUnavailableError
from auto_control_script.core.frame import Frame
from auto_control_script.core.target import KIND_WINDOW
from auto_control_script.core.window_manager import WindowManager

PATH_PRINTWINDOW = "printwindow"
"""str: 取图路径——PrintWindow（PW_RENDERFULLCONTENT）。"""

PATH_BITBLT = "bitblt"
"""str: 取图路径——BitBlt 拷贝窗口 DC。"""

PATH_WGC = "wgc"
"""str: 取图路径——Windows Graphics Capture 后台会话。"""

PW_RENDERFULLCONTENT = 2
"""int: PrintWindow 的 PW_RENDERFULLCONTENT 标志，用于抓取合成后的完整窗口内容。"""

WGC_FRAME_TIMEOUT = 5.0
"""float: WGC 会话启动后等待首帧的超时时间（秒）。"""

logger = logging.getLogger(__name__)

_user32 = ctypes.windll.user32
_user32.PrintWindow.argtypes = [ctypes.c_ssize_t, ctypes.c_ssize_t, ctypes.c_uint]
_user32.PrintWindow.restype = ctypes.c_int


def _print_window(hwnd: int, hdc: int, flags: int) -> bool:
    """
    调用 Win32 PrintWindow 抓取窗口内容。

    pywin32 的 win32gui 未提供 PrintWindow，故直接用 ctypes 调用 user32。

    Args:
        hwnd (int): 窗口句柄
        hdc (int): 目标设备上下文句柄
        flags (int): 取图标志，PW_RENDERFULLCONTENT 表示抓取合成后的完整内容

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    return bool(_user32.PrintWindow(hwnd, hdc, flags))


def wgc_installed() -> bool:
    """
    判断 WGC 取图路径是否可用（windows-capture 包已安装）。

    Returns:
        bool: 可用返回 True，否则 False
    """
    try:
        import windows_capture  # noqa: F401
    except ImportError:
        return False
    return True


def auto_order() -> list:
    """
    获取 auto 模式下的取图路径尝试顺序。

    Returns:
        list: 取图路径列表，WGC 已安装时插在 printwindow 与 bitblt 之间
    """
    order = [PATH_PRINTWINDOW]
    if wgc_installed():
        order.append(PATH_WGC)
    order.append(PATH_BITBLT)
    return order


def _grab_gdi(hwnd: int, width: int, height: int, use_print_window: bool) -> numpy.ndarray:
    """
    用 GDI 方式抓取整个窗口（含边框与标题栏）的像素。

    Args:
        hwnd (int): 窗口句柄
        width (int): 抓取宽度（窗口整体宽度）
        height (int): 抓取高度（窗口整体高度）
        use_print_window (bool): True 用 PrintWindow，False 用 BitBlt

    Returns:
        numpy.ndarray: BGR 顺序的像素数组，形状为 (height, width, 3)

    Raises:
        CaptureError: 取图失败时抛出
    """
    window_dc = win32gui.GetWindowDC(hwnd)
    if not window_dc:
        raise CaptureError(
            f"capture_win._grab_gdi: GetWindowDC 失败，窗口 {hwnd} 可能已失效"
        )
    try:
        mfc_dc = win32ui.CreateDCFromHandle(window_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)
        try:
            if use_print_window:
                ok = _print_window(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
                if not ok:
                    raise CaptureError(
                        f"capture_win._grab_gdi: PrintWindow 返回失败，窗口 {hwnd}，"
                        f"请求尺寸={width}x{height}"
                    )
            else:
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
            bits = bitmap.GetBitmapBits(True)
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
    finally:
        win32gui.ReleaseDC(hwnd, window_dc)
    array = numpy.frombuffer(bits, dtype=numpy.uint8).reshape(height, width, 4)
    return array[:, :, :3].copy()


class WgcSession:
    """
    WGC 后台取图会话。

    启动一个后台线程持续接收窗口帧，capture() 只取最近一帧，
    因此适合高频取图；不用时必须 stop() 释放。

    Attributes:
        hwnd (int): 窗口句柄
    """

    def __init__(self, hwnd: int):
        """
        初始化 WGC 会话（此时尚未启动线程）。

        Args:
            hwnd (int): 窗口句柄

        Raises:
            ChannelUnavailableError: windows-capture 包未安装时抛出
        """
        if not wgc_installed():
            raise ChannelUnavailableError(
                "capture_win.WgcSession: 未安装可选的 WGC 取图依赖 windows-capture，"
                "无法使用 wgc 取图路径；执行 `pip install windows-capture` 后可启用，"
                "不安装时仍可使用 printwindow / bitblt 路径"
            )
        self.hwnd = hwnd
        self._latest = None
        self._lock = threading.Lock()
        self._control = None
        self._closed = False

    def start(self) -> None:
        """
        启动 WGC 后台取图线程并等待首帧到达。

        Raises:
            CaptureError: 首帧在超时时间内未到达时抛出
        """
        from windows_capture import WindowsCapture

        capture = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            window_hwnd=self.hwnd,
        )
        holder = self

        @capture.event
        def on_frame_arrived(frame_obj, _control):
            holder._set_latest(frame_obj.convert_to_bgr().frame_buffer.copy())

        @capture.event
        def on_closed():
            holder._closed = True

        self._control = capture.start_free_threaded()
        deadline = time.time() + WGC_FRAME_TIMEOUT
        while time.time() < deadline:
            with self._lock:
                if self._latest is not None:
                    return
            time.sleep(0.05)
        raise CaptureError(
            f"capture_win.WgcSession.start: WGC 会话启动后 {WGC_FRAME_TIMEOUT} 秒内未收到首帧，"
            f"窗口 {self.hwnd} 可能不支持 Windows Graphics Capture"
        )

    def _set_latest(self, pixels: numpy.ndarray) -> None:
        """
        记录最新一帧。

        Args:
            pixels (numpy.ndarray): BGR 像素数组
        """
        with self._lock:
            self._latest = pixels

    def grab(self) -> numpy.ndarray:
        """
        取最新一帧的拷贝。

        Returns:
            numpy.ndarray: BGR 像素数组

        Raises:
            CaptureError: 尚未收到任何帧，或会话已关闭时抛出
        """
        with self._lock:
            if self._latest is None:
                raise CaptureError(
                    f"capture_win.WgcSession.grab: 尚未收到任何帧，窗口 {self.hwnd}"
                )
            latest = self._latest
        if self._closed:
            raise CaptureError(
                f"capture_win.WgcSession.grab: WGC 会话已关闭，窗口 {self.hwnd}"
            )
        return latest.copy()

    def stop(self) -> None:
        """停止 WGC 后台线程并释放会话。"""
        if self._control is not None:
            self._control.stop()
            self._control = None


_WGC_SESSIONS: dict = {}
"""dict: hwnd -> WgcSession 的会话缓存，避免每次取图都新建会话。"""


def _grab_wgc(hwnd: int) -> numpy.ndarray:
    """
    用 WGC 会话抓取窗口像素，会话按窗口缓存复用。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        numpy.ndarray: BGR 像素数组
    """
    session = _WGC_SESSIONS.get(hwnd)
    if session is None:
        session = WgcSession(hwnd)
        session.start()
        _WGC_SESSIONS[hwnd] = session
    return session.grab()


def release(hwnd: Optional[int] = None) -> None:
    """
    释放取图资源（WGC 会话与 GDI 缓存）。

    Args:
        hwnd (int): 要释放的窗口句柄，None 表示释放全部
    """
    if hwnd is None:
        for session in list(_WGC_SESSIONS.values()):
            session.stop()
        _WGC_SESSIONS.clear()
        return
    session = _WGC_SESSIONS.pop(hwnd, None)
    if session is not None:
        session.stop()


def _crop_to_client(full: numpy.ndarray, manager: WindowManager, path: str,
                    assume_full_window: bool = True) -> Frame:
    """
    把取到的像素裁剪为客户区，并构造 Frame。

    当 assume_full_window 为 False 时，认为取到的像素已经是客户区，不再裁剪；
    该模式用于 WGC 等可能直接返回客户区内容的路径。

    Args:
        full (numpy.ndarray): 取到的像素数组
        manager (WindowManager): 已刷新的窗口几何管理器
        path (str): 实际使用的取图路径，写入 Frame
        assume_full_window (bool): 像素是否包含窗口边框与标题栏

    Returns:
        Frame: 客户区画面帧

    Raises:
        CaptureError: 整窗尺寸与窗口几何不符，或裁剪区域越界时抛出
    """
    full_height, full_width = full.shape[:2]
    if not assume_full_window:
        if (full_width, full_height) != (manager.pixel_width, manager.pixel_height):
            raise CaptureError(
                f"capture_win._crop_to_client: 取图路径 {path} 未按客户区返回，尺寸为 "
                f"{full_width}x{full_height}，客户区像素尺寸为 {manager.pixel_width}x"
                f"{manager.pixel_height}"
            )
        return Frame(
            pixels=full.copy(),
            width=manager.pixel_width,
            height=manager.pixel_height,
            target_id=str(manager.hwnd),
            path=path,
        )
    if (full_width, full_height) != (manager.window_width, manager.window_height):
        raise CaptureError(
            f"capture_win._crop_to_client: 取图路径 {path} 返回的整窗尺寸为 "
            f"{full_width}x{full_height}，与窗口几何 {manager.window_width}x"
            f"{manager.window_height} 不一致，无法裁剪出客户区；"
            f"窗口 {manager.hwnd}（{manager.title!r}）可能在取图过程中发生了尺寸变化"
        )
    x1 = manager.offset_x
    y1 = manager.offset_y
    x2 = x1 + manager.pixel_width
    y2 = y1 + manager.pixel_height
    if x2 > full_width or y2 > full_height:
        raise CaptureError(
            f"capture_win._crop_to_client: 客户区裁剪区域 ({x1}, {y1}, {x2}, {y2}) 超出整窗范围 "
            f"{full_width}x{full_height}，取图路径={path}，窗口 {manager.hwnd}"
        )
    return Frame(
        pixels=full[y1:y2, x1:x2].copy(),
        width=manager.pixel_width,
        height=manager.pixel_height,
        target_id=str(manager.hwnd),
        path=path,
    )


def capture_window(hwnd: int, path: str = PATH_AUTO) -> Frame:
    """
    截取指定窗口的客户区画面。

    Args:
        hwnd (int): 窗口句柄
        path (str): 取图路径，auto / printwindow / bitblt / wgc；
            显式指定时只尝试该路径，失败即报错不回退

    Returns:
        Frame: 客户区画面帧，坐标原点为客户区左上角

    Raises:
        ChannelUnavailableError: 指定了不可用或未知的取图路径时抛出
        CaptureError: 所有候选路径均失败时抛出，消息含每条路径的失败原因
    """
    known_paths = (PATH_AUTO, PATH_PRINTWINDOW, PATH_BITBLT, PATH_WGC)
    if path not in known_paths:
        raise ChannelUnavailableError(
            f"window_capture.capture_window: 未知取图路径 {path!r}，可选值为 {list(known_paths)}"
        )
    if path == PATH_WGC and not wgc_installed():
        raise ChannelUnavailableError(
            f"window_capture.capture_window: 未安装可选的 WGC 取图依赖 windows-capture，"
            f"无法使用 wgc 路径；执行 `pip install windows-capture` 后可启用"
        )

    candidates = auto_order() if path == PATH_AUTO else [path]
    manager = WindowManager(hwnd)
    failures = []
    for candidate in candidates:
        try:
            manager.refresh()
            if candidate == PATH_PRINTWINDOW:
                full = _grab_gdi(hwnd, manager.window_width, manager.window_height, True)
                result = _crop_to_client(full, manager, candidate)
            elif candidate == PATH_BITBLT:
                full = _grab_gdi(hwnd, manager.window_width, manager.window_height, False)
                result = _crop_to_client(full, manager, candidate)
            elif candidate == PATH_WGC:
                full = _grab_wgc(hwnd)
                full_height, full_width = full.shape[:2]
                is_full_window = (full_width, full_height) == (
                    manager.window_width, manager.window_height)
                is_client = (full_width, full_height) == (
                    manager.pixel_width, manager.pixel_height)
                if not (is_full_window or is_client):
                    raise CaptureError(
                        f"window_capture.capture_window: WGC 返回的帧尺寸为 "
                        f"{full_width}x{full_height}，既不等于窗口整体 "
                        f"{manager.window_width}x{manager.window_height}，也不等于客户区 "
                        f"{manager.pixel_width}x{manager.pixel_height}，无法把图像坐标与"
                        f"点击坐标对齐；窗口 {hwnd}（{manager.title!r}）；"
                        f"请改用 printwindow 或 bitblt 路径"
                    )
                result = _crop_to_client(full, manager, candidate, is_full_window)
            else:
                raise ChannelUnavailableError(
                    f"window_capture.capture_window: 未知取图路径 {candidate!r}，"
                    f"可选值为 {list(known_paths)}"
                )
            frame_module.validate(result)
            logger.info(
                f"window_capture.capture_window: 取图成功，窗口={hwnd}，路径={candidate}，"
                f"客户区={result.width}x{result.height}"
            )
            return result
        except (CaptureError, ChannelUnavailableError) as error:
            reason = str(error)
            failures.append(f"[{candidate}] {reason}")
            logger.warning(
                f"window_capture.capture_window: 取图路径 {candidate} 失败，"
                f"窗口={hwnd}，原因={reason}"
            )
            if candidate == PATH_WGC:
                release(hwnd)

    raise CaptureError(
        f"window_capture.capture_window: 窗口 {hwnd} 的全部候选取图路径均失败 "
        f"（候选={candidates}）：\n" + "\n".join(failures)
    )


class WindowCapture(BaseCapture):
    """
    Windows 窗口截图器。

    Attributes:
        kind (str): 固定为 KIND_WINDOW
        paths (tuple): 支持的取图路径
    """

    kind = KIND_WINDOW
    paths = (PATH_AUTO, PATH_PRINTWINDOW, PATH_BITBLT, PATH_WGC)

    def grab(self, target, path: str) -> Frame:
        """
        按指定路径截取窗口客户区画面。

        Args:
            target (Target): 窗口目标
            path (str): 取图路径

        Returns:
            Frame: 客户区画面帧
        """
        return capture_window(int(target.id), path)

    def release(self, target=None) -> None:
        """
        释放窗口取图会话。

        Args:
            target (Target): 窗口目标，None 表示释放全部窗口的会话
        """
        release(int(target.id) if target else None)
