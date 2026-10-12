# -*- coding: utf-8 -*-
"""
core - 基础设施层

职责:
- 提供被所有能力包共享、且不依赖任何能力包的基础设施

包含:
- settings.py: 配置与用户目录
- errors.py: 异常类型与错误码
- frame.py: 画面帧数据契约
- logger.py: 日志记录器
- target.py: 目标抽象（窗口与设备的统一表示）
- window_manager.py: 窗口几何与坐标换算
"""
