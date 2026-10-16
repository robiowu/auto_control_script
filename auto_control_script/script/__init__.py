# -*- coding: utf-8 -*-
"""
script - 脚本能力包

职责:
- 脚本的数据模型与执行

包含:
- base.py: BaseRunner 运行器抽象基类（与其它能力包一致的抽象约定）
- factory.py: create_runner 运行器工厂，按目标类型分派具体实现
- model.py: Script / Step / RunSession / StepRecord 与校验
- runner.py: 脚本执行引擎（运行控制、快照、逐步记录）
"""
