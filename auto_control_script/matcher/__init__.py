# -*- coding: utf-8 -*-
"""
matcher - 查找能力包

职责:
- 在画面中按图或按字定位，统一返回可直接点击的坐标

包含:
- base.py: MatchResult 查找结果
- factory.py: find_by_image() / find_by_text() 对外入口
- image_matcher.py: OpenCV 模板匹配
- text_matcher.py: 基于 OCR 结果的文字定位
"""
