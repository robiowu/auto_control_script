# -*- coding: utf-8 -*-
"""
ocr - 文字识别能力包

职责:
- 按通道选择 OCR 引擎并统一输出结构

包含:
- base.py: TextItem / OcrResult 与 BaseOcr 抽象基类
- factory.py: create_ocr() 工厂与 recognize() 对外入口
- builtin_ocr.py: 系统内置通道（零安装、不提供置信度）
- precise_ocr.py: 高精度通道（PP-OCRv4、提供真实置信度）
- utils.py: 从识别文本中提取结构化信息
"""
