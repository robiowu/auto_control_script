## Why

项目当前代码结构与 `.codemaker/rules/` 中定义的代码风格、模块结构等规范存在较大偏差，且包名 `ScriptElf` 与 git 仓库名 `auto_control_script` 不一致。本次重构将项目统一到当前规则框架下。

## What Changes

- **BREAKING**: 包名从 `ScriptElf` 重命名为 `auto_control_script`，所有模块路径变更
- **BREAKING**: `setup.py` 中包名和描述更新为 `auto_control_script`
- **BREAKING**: `__init__.py` 清空（遵循 `python-02-模块结构` 的 `__init__.py` 最小化原则）
- 所有内部导入改用完整路径（如 `from auto_control_script.winhandle import Window`），去除对 `__init__.py` 重导出的依赖
- 所有模块添加文件头 docstring，遵循 `general-01-代码风格` 规范
- 所有函数添加参数类型和返回值注释
- `registryExt.py` 注释从 GBK 乱码修复为 UTF-8
- 移除 `print` 调试残留，统一使用模块内定义的 Logger
- `requirements.txt` 对齐实际依赖
- 根目录 `README.md` 统一项目说明，不再额外新增文档文件

## Capabilities

### New Capabilities

- `window-capture`: 窗口截图与图像识别能力。通过 Windows API 获取指定窗口的截图，支持模板匹配（大图找小图）、特征图定位。
- `adb-control`: ADB 设备控制能力。通过 ADB 协议对 Android 设备进行截图、点击、滑动、应用启停等操作。
- `game-automation`: 游戏自动化基类能力。提供基于特征图识别的游戏脚本框架，支持窗口管理、日志记录、随机点击等通用操作。
- `system-utils`: 系统工具能力。包含注册表读写、文件复制/移动/删除、命令行同步/异步执行等基础系统操作。

### Modified Capabilities

（无已有能力，本次为首次规范化）

## Impact

- 所有模块文件路径变化：`ScriptElf/` → `auto_control_script/`
- `__init__.py` 从有 `__all__` 导出声明的状态变为空文件，调用方需改用完整路径导入
- `setup.py` 中 `name` 字段变更，若有 pip install 依赖需更新
- 内部调用方（如 `gamecase.py` 中的 `import ScriptElf.xxx`）需同步更新
