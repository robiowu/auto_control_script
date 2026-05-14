# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name="auto_control_script",
    version="2.4",
    description="Windows 游戏自动化工具库 —— 窗口截图、图像识别、ADB 控制",
    license="GPL Licence",
    author="robiowu",
    packages=['auto_control_script'],
    platforms="windows",
    install_requires=['pywin32', 'opencv-python', 'pillow', 'numpy', 'pyautogui'],
)
