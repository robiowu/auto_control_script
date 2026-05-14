## 1. 目录与文件重命名

- [x] 1.1 使用 `git mv` 将 `ScriptElf/` 目录重命名为 `auto_control_script/`
- [x] 1.2 模块文件重命名为 snake_case：`adbUtils.py` → `adb_utils.py`、`findpic.py` → `find_pic.py`、`gamecase.py` → `game_case.py`、`mylog.py` → `my_log.py`、`registryExt.py` → `registry_ext.py`、`winhandle.py` → `win_handle.py`、`system_cmd.py` 保持不变

## 2. 包结构规范化

- [x] 2.1 清空 `auto_control_script/__init__.py`，移除 `__all__` 声明，添加空文件注释（注明包名和用途）
- [x] 2.2 更新所有内部导入为完整路径（如 `from auto_control_script.win_handle import Window`），逐一修改 `adb_utils.py`、`find_pic.py`、`game_case.py`

## 3. 模块规范化 —— 无内部依赖的先改

- [x] 3.1 `system_cmd.py`：添加文件头 docstring，所有函数添加类型注释和 docstring（`copy`、`move`、`cmd_block`、`cmd_asyn`、`remove_file`、`remove_folder`、`get_abs_appdata_path`）
- [x] 3.2 `my_log.py`：添加文件头 docstring，`Logger.__init__` 添加类型注释和 docstring
- [x] 3.3 `registry_ext.py`：修复文件编码声明为 `# -*- coding: utf-8 -*-`，将 GBK 乱码注释翻译为可读中文，所有函数添加类型注释和 docstring
- [x] 3.4 `win_handle.py`：添加文件头 docstring，所有函数（`find_idxSubHandle`、`find_listSubHandle`、`find_sub_handle`、`leftclick`、`leftclickXY`）和 `Window` 类的方法添加类型注释和 docstring
- [x] 3.5 `find_pic.py`：添加文件头 docstring，所有函数（`get_cv2_numpy_image_from_file`、`get_cv2_numpy_image_from_PyCBitmap`、`find_sub_pic`）和 `FindPictureHelper` 类的方法添加类型注释和 docstring，移除 `__main__` 中的死代码注释块
- [x] 3.6 `adb_utils.py`：添加文件头 docstring，`AdbUtils` 类及所有方法添加类型注释和 docstring，`print` 方法移除对 `self.__dict__` 的 `"logger"` 检查改用 `getattr`，`__lunch__` 重命名为 `launch_app`

## 4. 模块规范化 —— 有内部依赖的后改

- [x] 4.1 `game_case.py`：更新所有 import 为新包名和文件名，添加文件头 docstring，`FeaturePic` 和 `MyGameCase` 类及方法添加类型注释和 docstring，移除注释掉的无用代码块，`__log_init` 重命名为 `_log_init`

## 5. 项目配置更新

- [x] 5.1 更新 `setup.py`：`name` 改为 `auto_control_script`，`description` 更新为项目实际用途，`packages` 从 `find_packages()` 改为显式 `['auto_control_script']`
- [x] 5.2 更新 `requirements.txt`：对齐 `setup.py` 中的 `install_requires`，移除未直接使用的依赖

## 6. 验证

- [x] 6.1 在 Conda 环境中执行 `python -c "from auto_control_script.system_cmd import get_abs_appdata_path; print(get_abs_appdata_path())"` 验证导入正常
- [x] 6.2 检查所有模块无 `print` 调试残留、无死代码注释块、无中文路径引用
