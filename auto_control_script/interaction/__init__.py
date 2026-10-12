# -*- coding: utf-8 -*-
"""
interaction - 输入能力包

职责:
- 按目标类型与执行方式分派到对应的输入实现

包含:
- base.py: Action 数据契约与 BaseInteraction 抽象基类
- factory.py: create_interaction() 工厂与 perform() 对外入口
- key_codes.py: 键名到虚拟键码的映射
- win_background.py: Windows 后台消息输入
- win_foreground.py: Windows 前台真实键鼠输入
- adb_input.py: 安卓设备输入
"""
