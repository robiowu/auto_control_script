# auto_control_script

Windows / 安卓自动化工具平台：统一的**截图**、**输入**、**OCR** 能力，加上按键精灵式的**脚本编排**与一套零构建的**网页界面**。

三类使用方式，同一套底层能力：

| 使用方式 | 适合谁 | 入口 |
|---|---|---|
| 库调用 | 写 Python 脚本的开发者 | `from auto_control_script.capture import factory as capture` 等，见[库调用](#库调用) |
| 命令行 | 想快速截一张图、识别一段文字、点一下 | `python -m auto_control_script <子命令>` |
| 网页界面 | 不想写代码、要可视化编排流程 | `python -m auto_control_script web` |

## 安装

```bash
conda run -n python313 pip install -r requirements.txt
# 或以库的形式安装
conda run -n python313 pip install .
```

环境约定：使用 conda 环境 `python313`（Python 3.13）。中文输出前先声明编码，避免终端用 GBK 解码报错：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
```

## 核心概念

只有三个概念需要先理解，其余都是它们的组合。

**目标（Target）**：一次自动化的载体，可以是一个 Windows 窗口或一台安卓设备。所有能力都要求先指定目标。

```text
python -m auto_control_script targets --json
```

输出中 `id` 是稳定标识（窗口为句柄、设备为 serial），可直接作为 `--target` 的参数。

**画面帧（Frame）**：一次截图的产物，含像素、尺寸、采集时间与实际取图路径。它是 OCR 与模板匹配的唯一输入。

**坐标**：全平台统一为**以目标客户区左上角为原点的图像像素坐标**。窗口边框与 DPI 缩放在取图阶段就已处理完毕，所以「图像上看到哪里」就是「点击会点在哪里」，不需要任何人工偏移量。

## 命令行

| 子命令 | 作用 |
|---|---|
| `targets` | 列出可用窗口与设备 |
| `capture` | 截图保存为图片 |
| `ocr` | 识别目标画面或图片文件中的文字 |
| `input` | 下发一次点击 / 输入 / 按键等动作 |
| `run` | 运行脚本 |
| `script` | 脚本校验与查看 |
| `web` | 启动网页界面 |

全部子命令支持 `--json`（机器可读输出）与 `--verbose`（输出关键决策日志），两者可写在子命令前后任意位置。

```powershell
python -m auto_control_script targets --json
python -m auto_control_script capture --target 466954 --out screen.png --json
python -m auto_control_script ocr --image screen.png --json
python -m auto_control_script ocr --target 466954 --channel precise --json
python -m auto_control_script input --target 466954 --action click --point 100,200
python -m auto_control_script input --target 466954 --action input_text --text "中文abc123"
python -m auto_control_script run --script my_flow.json --target 466954
python -m auto_control_script script validate --script my_flow.json
python -m auto_control_script web
```

退出码：`0` 成功；`2` 参数或脚本非法；`3` 目标不可用；`4` 执行失败；`5` 依赖缺失。

## 库调用

每个能力包都用 `factory` 作为对外入口，直接 `import ... as` 成短名字即可：

```python
from auto_control_script.capture import factory as capture
from auto_control_script.core import target as target_module
from auto_control_script.interaction import factory as interaction
from auto_control_script.interaction.base import ACTION_CLICK, Action
from auto_control_script.matcher import factory as matcher
from auto_control_script.ocr import factory as ocr

targets = target_module.list_targets()          # 枚举目标
game = target_module.resolve_target("窗口标题")  # 解析目标

frame = capture.capture(game)            # 截图（默认后台，窗口被遮挡也能取到）
result = ocr.recognize(frame)           # OCR，result.channel 标明实际使用的通道
hit = matcher.find_by_text(frame, "登录")  # 按字查找
if hit.found:
    interaction.perform(game, Action(     # 后台点击，不抢焦点
        kind=ACTION_CLICK, point=hit.point, mode="background"))
```

需要直接拿到某个实现时，用工厂而不是自己 new：

```python
from auto_control_script.capture.factory import create_capture
from auto_control_script.interaction.factory import create_interaction
from auto_control_script.ocr.factory import create_ocr

capture_impl = create_capture(game.kind)                  # WindowCapture / AdbCapture
input_impl = create_interaction(game.kind, "background")  # 后台或前台
ocr_impl = create_ocr("precise")                          # 指定通道，缺失即报错
```

坐标、图像、动作三类对象在 Windows 窗口与安卓设备上语义完全一致，同一段脚本改绑目标即可换端运行。

## 网页界面

```powershell
python -m auto_control_script web
```

默认只监听本机回环地址 `http://127.0.0.1:8770/`，浏览器中完成：选目标 → 看预览 → 在画面上框选取点 → 添加步骤 → 保存 → 运行 → 看日志与快照。运行中可暂停、继续、停止、单步、重试本步。

页面关闭不会终止正在运行的脚本；重新打开后可查看历史运行记录与快照。

## 三种取图路径

| 路径 | 依赖 | 适用 |
|---|---|---|
| `printwindow`（默认） | 无额外依赖 | 绝大多数桌面窗口，被遮挡也能取到内容 |
| `bitblt` | 无额外依赖 | PrintWindow 取不到时的备选 |
| `wgc` | 需安装 `windows-capture` | 全屏渲染、游戏类窗口 |

`auto` 模式按 `printwindow → wgc（已安装时）→ bitblt` 顺序尝试，每次切换都写入日志；**显式指定路径时只尝试该路径，失败即报错，不会偷偷换路径**。

## OCR 通道

平台同时提供两类通道，**默认自动选择**：高精度通道可用时优先，否则使用系统内置通道。每次识别结果的 `channel` 字段都会标明本次实际用的是哪一类。

| 通道 | 开箱即用 | 置信度 | 说明 |
|---|---|---|---|
| `builtin` 系统内置 | 是（需系统 OCR 语言包） | **不提供** | 零模型下载，识别结果中 `confidence` 为 `None`、`confidence_available=False`，不伪造数值 |
| `precise` 高精度 | 需安装依赖 | 提供真实置信度 | PP-OCRv4 模型，精度显著更高 |

需要按置信度过滤结果时，必须启用高精度通道。

### 启用高精度 OCR 通道（从零开始）

**1. 安装依赖**

```bash
conda run -n python313 pip install rapidocr-onnxruntime onnxruntime
```

模型随包附带、首次使用时自动加载，无需手工下载；体积约百 MB，纯 CPU 推理即可。

**2. 确认已生效**

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python -m auto_control_script ocr --image screen.png --channel precise --json
```

返回的 `channel` 为 `precise`、`confidence_available` 为 `true` 即表示已生效。

不带 `--channel` 时，通道为自动选择：高精度依赖已安装就会自动使用它，结果中的 `channel_reason` 会说明选择原因。

**3. 常见问题排查**

| 现象 | 原因与处理 |
|---|---|
| 提示「未安装高精度 OCR 通道依赖」 | 未执行上面的安装命令；执行后重新运行即可 |
| 安装后仍然走系统内置通道 | 在其它 conda 环境里装的；确认 `conda run -n python313 pip list` 能看到 `rapidocr-onnxruntime` |
| 首次识别很慢 | 首次调用要加载模型，属正常现象；后续调用在同一进程内复用引擎 |
| 进程直接崩溃、无任何报错 | 见下方「已知环境限制」 |

### 系统内置通道的语言包

系统内置通道依赖 Windows OCR 语言包。查看已安装的语言：

```powershell
python -m auto_control_script ocr --image screen.png --channel builtin --json
```

若提示缺少语言包，按报错信息中的命令以管理员身份安装，例如中文：

```powershell
Add-WindowsCapability -Online -Name "Language.OCR~~~zh-Hans-CN~0.0.1.0"
```

## 已知环境限制

**onnxruntime 与 winocr 的加载顺序冲突**：在同一进程内，先加载系统内置通道（winocr）再加载高精度通道（onnxruntime）会导致进程直接崩溃（访问冲突 `0xC0000005`，无法被异常捕获）。

平台已自动规避：任何可能加载 winocr 的路径都会先导入高精度通道的底层库。因此**正常使用不会触发**；但若在自己的脚本里手工 `import winocr` 后再使用高精度通道，仍可能触发。规避方式是让 `import rapidocr_onnxruntime` 先于 `import winocr`，或两类通道分别在不同的进程中运行。

**后台输入无法验证生效**：后台消息投递返回成功只代表消息已入队，不代表目标应用真的处理了它。平台不会假装成功——需要确认结果时，请在脚本中加一步「截图比对」。

**安卓侧的文本输入**：`adb shell input text` 只支持 ASCII，向设备输入中文会直接报错，不会静默输入乱码。

**WGC 取图的尺寸对齐**：部分窗口的 WGC 帧尺寸既不等于窗口整体也不等于客户区，此时会报错并提示改用 `printwindow` / `bitblt`，不会猜测式裁剪。

## 配置

配置文件：`%APPDATA%/auto_control_script/settings.json`（不存在时使用内置默认值）。可配置项包括 adb 路径、默认取图路径、默认 OCR 通道与语言、默认输入方式（后台 / 前台）、动作节奏与抖动、运行记录保留上限、网页监听地址与端口。

写入未知的配置键会在启动时明确报错，而不是被当成「未设置」静默忽略。

## 模块一览

按**能力**分包，每个能力包固定四件套：`base.py`（抽象基类）+ `factory.py`（工厂与对外入口）+ 平台实现文件 + `__init__.py`。

```text
auto_control_script/
├── core/                     # 基础设施层：不依赖任何能力包
│   ├── settings.py           # 配置与用户目录
│   ├── errors.py             # 异常类型与错误码
│   ├── frame.py              # 画面帧数据契约
│   ├── logger.py             # 日志记录器
│   ├── target.py             # 目标抽象：窗口与设备的枚举、解析、刷新
│   └── window_manager.py     # 窗口几何：客户区尺寸、缩放比、坐标换算、置顶
├── capture/                  # 截图能力
│   ├── base.py               # BaseCapture 抽象基类 + 取图路径常量
│   ├── factory.py            # create_capture()：按目标类型分派
│   ├── window_capture.py     # Windows 取图：printwindow / bitblt / wgc
│   └── adb_capture.py        # 安卓取图
├── interaction/              # 输入能力
│   ├── base.py               # Action 契约 + BaseInteraction 抽象基类
│   ├── factory.py            # create_interaction()：按目标类型与执行方式分派
│   ├── key_codes.py          # 按键名到虚拟键码的映射
│   ├── win_background.py     # Windows 后台消息输入（不抢焦点）
│   ├── win_foreground.py     # Windows 前台真实键鼠输入
│   └── adb_input.py          # 安卓输入
├── ocr/                      # 文字识别能力
│   ├── base.py               # TextItem / OcrResult + BaseOcr 抽象基类
│   ├── factory.py            # create_ocr()：按通道分派
│   ├── builtin_ocr.py        # 系统内置通道（零安装，不提供置信度）
│   ├── precise_ocr.py        # 高精度通道（PP-OCRv4，提供真实置信度）
│   └── utils.py              # 从文本中提取数字/金额/时间/百分比
├── matcher/                  # 查找能力
│   ├── base.py               # MatchResult 查找结果
│   ├── factory.py            # find_by_image() / find_by_text()
│   ├── image_matcher.py      # OpenCV 模板匹配
│   └── text_matcher.py       # 基于 OCR 结果的文字定位
├── script/                   # 脚本能力
│   ├── model.py              # Script / Step / RunSession / StepRecord 与校验
│   └── runner.py             # 脚本执行引擎（运行控制、快照、逐步记录）
├── utils/                    # 通用工具
│   ├── adb.py                # adb 命令封装与设备枚举
│   ├── system_cmd.py         # 系统命令与文件操作
│   └── registry_ext.py       # Windows 注册表操作
├── case.py                   # 自动化用例基类
├── cli.py                    # 命令行
└── web/                      # 网页界面（服务端与静态资源）
```

新增一个平台实现只需三步：写实现文件、在 `factory.py` 加一个分支、在包 `__init__.py` 的 docstring 里登记。

脚本、运行记录与日志存放在 `%APPDATA%/auto_control_script/` 下的 `scripts/`、`runs/`、`logs/`。
