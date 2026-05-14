# -*- coding: utf-8 -*-
"""
win_handle.py - Windows 窗口句柄操作模块

职责:
- 提供子窗口句柄查找（按类名/标题/索引）
- 提供窗口鼠标点击（SendMessage 方式和 pyautogui 全模拟方式）
- 提供窗口显示控制（显示/隐藏/置顶/取消置顶/高亮/缩放）

调用链:
- game_case.py -> win_handle.py -> win32gui / win32api / win32con / pyautogui
"""
import win32gui
import win32api
import win32con
import pyautogui
import time
import random


def find_idxSubHandle(pHandle: int, winClass: str, winName: str, index: int = 0) -> int:
    """
    已知子窗口的类名和标题，寻找第 index 个同类型兄弟窗口。

    Args:
        pHandle (int): 父窗口句柄，无父窗口则置 0
        winClass (str): 待查找窗口的类名，None 表示不限类名（不能与 winName 同时为 None）
        winName (str): 待查找窗口的标题，None 表示不限标题（不能与 winClass 同时为 None）
        index (int): 待查找窗口的顺序值，>= 0

    Returns:
        int: 查找到的窗口句柄
    """
    assert (type(index) == int and index >= 0)
    assert (winClass is not None or winName is not None)
    handle = 0
    for i in range(index + 1):
        handle = win32gui.FindWindowEx(pHandle, handle, winClass, winName)
    return handle


def find_listSubHandle(pHandle: int, winClass: str, winName: str) -> list:
    """
    查找满足条件的所有同类型子窗口。

    Args:
        pHandle (int): 父窗口句柄，无父窗口则置 0
        winClass (str): 待查找窗口的类名
        winName (str): 待查找窗口的标题

    Returns:
        list: 满足条件的兄弟窗口句柄列表
    """
    assert (winClass is not None or winName is not None)
    result_list = []
    handle = 0
    handle = win32gui.FindWindowEx(pHandle, handle, winClass, winName)
    while handle != 0:
        result_list.append(handle)
        handle = win32gui.FindWindowEx(pHandle, handle, winClass, winName)
    return result_list


def find_sub_handle(pHandle: int, winClassList: list) -> int:
    """
    按树状路径逐级查找子窗口句柄。

    Args:
        pHandle (int): 父窗口句柄
        winClassList (list[dict]): 每级子窗口的参数列表，
            每个 dict 包含 winClass、winName、index，对应 find_idxSubHandle() 的后三个参数

    Returns:
        int: 最终找到的子窗口句柄
    """
    assert type(winClassList) == list
    for args in winClassList:
        pHandle = find_idxSubHandle(pHandle, args["winClass"], args["winName"], args["index"])
    return pHandle


def leftclick(handle: int, long_position: int, move: bool = False) -> None:
    """
    在指定窗口的指定位置模拟左键点击（SendMessage 方式）。

    Args:
        handle (int): 目标窗口句柄
        long_position (int): 打包的鼠标坐标 LParam（通过 MAKELONG 生成）
        move (bool): 是否先发送 WM_MOUSEMOVE 消息
    """
    if move:
        win32gui.SendMessage(handle, win32con.WM_MOUSEMOVE, 0, long_position)
    wparam = 1
    win32gui.SendMessage(handle, win32con.WM_LBUTTONDOWN, wparam, long_position)
    time.sleep(0.2)
    win32gui.SendMessage(handle, win32con.WM_LBUTTONUP, wparam, long_position)


def leftclickXY(handle: int, x_position: int, y_position: int) -> tuple:
    """
    在指定窗口的 (x, y) 坐标处模拟左键点击。

    Args:
        handle (int): 目标窗口句柄
        x_position (int): 点击的横坐标（客户区坐标）
        y_position (int): 点击的纵坐标（客户区坐标）

    Returns:
        tuple: (x_position, y_position)
    """
    x_position = int(x_position)
    y_position = int(y_position)
    long_position = win32api.MAKELONG(x_position, y_position)
    leftclick(handle=handle, long_position=long_position)
    return x_position, y_position


class Window:
    """Windows 窗口操作封装"""

    hwnd: int = 0
    first_hwnd: int = 0

    def __init__(self, hwnd: int):
        """
        初始化窗口对象。

        Args:
            hwnd (int): 窗口句柄
        """
        self.hwnd = hwnd
        self.first_hwnd = self.hwnd

    def show(self) -> None:
        """显示窗口"""
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)

    def hide(self) -> None:
        """隐藏窗口"""
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)

    @property
    def ExStyle(self) -> int:
        """获取窗口扩展样式"""
        return win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)

    def setTop(self) -> None:
        """设置窗口置顶（保持当前位置和尺寸）"""
        temp_style = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        win32gui.SetWindowPos(self.first_hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, temp_style)

    def resetNotop(self) -> None:
        """取消窗口置顶（保持当前位置和尺寸）"""
        temp_style = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        win32gui.SetWindowPos(self.first_hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, temp_style)

    def randomClick(self, point_x: int, point_y: int, random_x: int = 0, random_y: int = 0,
                    full_mock: bool = False) -> tuple:
        """
        在窗口客户区指定位置模拟点击，支持随机偏移。

        Args:
            point_x (int): 客户区期望点击的左上角 X 坐标
            point_y (int): 客户区期望点击的左上角 Y 坐标
            random_x (int): X 方向随机偏移量，0 表示不随机
            random_y (int): Y 方向随机偏移量，0 表示不随机
            full_mock (bool): True 时使用 pyautogui 全模拟点击（移动鼠标到屏幕位置）

        Returns:
            tuple: (result_x, result_y) 实际点击坐标，坐标为负时返回 None
        """
        if point_x < 0 or point_y < 0:
            return
        random_x = int(random_x)
        random_y = int(random_y)
        result_x = point_x + random.randint(0, random_x)
        result_y = point_y + random.randint(0, random_y)
        if full_mock:
            self.setTop()
            left, top, _, _ = win32gui.GetWindowRect(self.hwnd)
            result_x += left
            result_y += top
            pyautogui.click(result_x, result_y, interval=0.2)
        else:
            result_x, result_y = leftclickXY(handle=self.hwnd, x_position=result_x, y_position=result_y)
        return result_x, result_y

    def highLight(self) -> None:
        """设置窗口边框高亮绘制"""
        temp_style = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_DRAWFRAME
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOP, 0, 0, 0, 0, temp_style)

    def noHighLight(self) -> None:
        """取消窗口边框高亮"""
        temp_style = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOP, 0, 0, 0, 0, temp_style)

    def resize(self, width: int, height: int) -> None:
        """
        调整窗口大小（保持当前位置）。

        Args:
            width (int): 目标宽度
            height (int): 目标高度
        """
        left, top, _, _ = win32gui.GetWindowRect(self.hwnd)
        win32gui.MoveWindow(self.hwnd, left, top, width, height, True)

    def restore(self) -> None:
        """恢复窗口至正常状态"""
        win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)


if __name__ == '__main__':
    for i in range(0, 100):
        print(random.randint(0, 0))
