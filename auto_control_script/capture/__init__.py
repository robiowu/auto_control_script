# -*- coding: utf-8 -*-
"""
capture - 截图能力包

职责:
- 按目标类型分派到对应平台的取图实现

包含:
- base.py: BaseCapture 抽象基类与取图路径常量
- factory.py: create_capture() 工厂与对外入口
- window_capture.py: Windows 窗口取图（printwindow / bitblt / wgc）
- adb_capture.py: 安卓设备取图
"""
