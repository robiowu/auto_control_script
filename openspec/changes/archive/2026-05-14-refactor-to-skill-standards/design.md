## Context

当前项目是一个 Windows 平台的游戏自动化工具库，提供窗口截图、图像识别、ADB 控制、窗口操作等能力。包名为 `ScriptElf`，使用 CamelCase 模块命名，`__init__.py` 包含 `__all__` 声明。需要重构以符合最新的 `.codemaker/rules/` 规范。

## Goals / Non-Goals

**Goals:**
- 包名重命名为 `auto_control_script`（对齐 git 仓库名）
- 模块文件名统一为 snake_case
- `__init__.py` 清空，遵循最小化原则
- 所有模块添加文件头 docstring 和函数类型注释
- 修复 `registryExt.py` 的 GBK 乱码
- 内部导入改用完整路径（`from auto_control_script.xxx import YYY`）

**Non-Goals:**
- 不改变任何模块的公开 API 行为
- 不新增功能模块
- 不引入新依赖
- 不创建测试代码（除非用户明确要求）

## Decisions

### 1. 模块文件名：CamelCase → snake_case

**选择**: 统一改为 snake_case，对齐 PEP 8 和 `python-02-模块结构` 示例风格。

| 旧名称 | 新名称 |
|--------|--------|
| `adbUtils.py` | `adb_utils.py` |
| `findpic.py` | `find_pic.py` |
| `gamecase.py` | `game_case.py` |
| `mylog.py` | `my_log.py` |
| `registryExt.py` | `registry_ext.py` |
| `system_cmd.py` | 不变（已是 snake_case） |
| `winhandle.py` | `win_handle.py` |

**理由**: 包名已是 BREAKING 变更，同步修正文件命名避免将来二次迁移。snake_case 是 Python 社区约定，`python-02-模块结构` 示例也使用 `client.py`、`handler.py` 格式。

**替代方案**: 保留原有 CamelCase 命名，仅改包名。但放弃了一次性规范化的机会，后续可能仍需迁移。

### 2. `__init__.py` 最小化

**选择**: 清空 `__init__.py`，移除 `__all__` 声明。

**理由**: 遵循 `python-02-模块结构` 规范——内部工程项目的 `__init__.py` 默认为空，不用于重导出。当前项目非 PyPI 公开发布库，无需 `__all__` 作为 API 边界。

### 3. 导入风格：完整路径导入

**选择**: 所有内部跨文件导入改用完整路径，如：
```python
from auto_control_script.win_handle import Window
from auto_control_script.my_log import Logger
```

**理由**: 遵循 `python-02-模块结构` 规范，明确导入来源，避免隐藏真实文件位置。

### 4. `registryExt.py` 编码修复

**选择**: 文件头 `# coding: gbk` 改为 `# -*- coding: utf-8 -*-`，乱码注释从 GBK 转写为可读 UTF-8 中文。

**理由**: 当前注释因 GBK→UTF-8 显示乱码不可读。源代码为 GBK 编码的中文注释，需用正确编码重新生成。

### 5. 模块组织不变

**选择**: 保持现有的 7 个模块边界，不拆分也不合并。

**理由**: 每个模块职责清晰：
- `adb_utils.py` — ADB 设备控制
- `find_pic.py` — 图像识别与窗口截图
- `game_case.py` — 游戏自动化基类
- `my_log.py` — 日志封装
- `registry_ext.py` — 注册表操作
- `system_cmd.py` — 系统命令工具
- `win_handle.py` — 窗口句柄操作

模块粒度适中，无需进一步拆分。

## Risks / Trade-offs

- **[BREAKING 变更]** 所有外部 import 路径失效 → 本项目为内部工具库，无已知外部 API 调用方，风险可控
- **[目录重命名]** `ScriptElf/` 目录改名后，git 历史可能断链 → 使用 `git mv` 保留历史
- **[registryExt.py 编码]** GBK 注释内容仅能从上下文推断原意 → 逐条确认注册表函数语义，确保注释准确
