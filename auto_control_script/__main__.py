# -*- coding: utf-8 -*-
"""
__main__.py - `python -m auto_control_script` 入口模块

职责:
- 把命令行参数转交给 cli.py 并以退出码结束进程

调用链:
- python -m auto_control_script -> __main__.py -> cli.py
"""

import sys

from auto_control_script.cli import main

if __name__ == "__main__":
    sys.exit(main())
