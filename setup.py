# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name="auto_control_script",
    version="3.0",
    description="Windows 自动化工具平台 —— 截图、输入、OCR、脚本编排与 Web 可视化",
    license="GPL Licence",
    author="robiowu",
    packages=[
        'auto_control_script',
        'auto_control_script.core',
        'auto_control_script.capture',
        'auto_control_script.interaction',
        'auto_control_script.ocr',
        'auto_control_script.matcher',
        'auto_control_script.script',
        'auto_control_script.utils',
        'auto_control_script.web',
    ],
    package_data={'auto_control_script.web': ['static/*']},
    platforms="windows",
    install_requires=[
        'pywin32', 'opencv-python', 'pillow', 'numpy',
        'pydirectinput', 'pyperclip', 'winocr',
        'fastapi', 'uvicorn',
    ],
    extras_require={
        'precise': ['rapidocr-onnxruntime', 'onnxruntime'],
        'wgc': ['windows-capture'],
    },
)
