# Implementation Plan: 统一截图·输入·OCR 自动化平台

**Branch**: `001-auto-control-platform` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-auto-control-platform/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

把参考项目 `game_deltaforce_factory` 的 capture / interaction / ocr 三层能力整合进 `game_auto_control_script`，并做本项目化重构：建立统一的「目标」抽象，让 Windows 窗口与安卓设备被同一套接口寻址；截图、输入、OCR 三类能力统一返回结构与坐标语义；在此之上提供按键精灵式的脚本编排能力；并新增一套 Web 界面，让后续使用者既能以 CLI / 库调用这些工具函数，也能在网页上可视化地拼出自动化脚本。

技术路线（详见 [research.md](./research.md)）：Web 层用 FastAPI + uvicorn + 零构建原生前端；OCR 采用双通道——系统内置通道开箱即用、高精度通道基于 onnxruntime 推理引擎可选启用；Windows 取图默认走 PrintWindow/BitBlt 并以 WGC 作为可选增强；前台输入用扫描码级输入以兼容全屏/游戏窗口，后台输入用窗口消息投递；ADB 侧沿用子进程调用官方 adb。所有来源的截图在取图层即裁剪为客户区并完成 DPI 换算，使「图像坐标 == 点击坐标」从根源成立，消除参考项目中硬编码偏移带来的耦合。

按决策 D1，本次为一次性破坏性重构：旧接口直接替换，不保留别名、兼容层与回退分支。

## Technical Context

**Language/Version**: Python 3.13（conda 环境 `python313`，实测 `3.13.13`）

**Primary Dependencies**:
- 既有保留：`pywin32`、`opencv-python`、`pillow`、`numpy`
- 输入：`pydirectinput`（前台真实键鼠，替换 `pyautogui`）、`pyperclip`（中文输入）
- OCR：`winocr`（系统内置通道）、`rapidocr-onnxruntime` + `onnxruntime`（高精度通道，可选依赖）
- 取图增强：`windows-capture`（WGC 后台取图，可选依赖）
- Web：`fastapi`、`uvicorn`

**Storage**: 文件系统（JSON）。脚本、运行记录与画面快照存放于用户目录 `%APPDATA%/auto_control_script/`，不使用数据库

**Testing**: pytest（仅在后续明确要求时编写测试；本轮验证以 `quickstart.md` 的端到端场景为准）

**Target Platform**: Windows 10 1809+ 桌面主机；安卓设备经 adb 接入（USB 或网络）

**Project Type**: library + cli + web（同一进程内：库为核心，CLI 与 Web 为其消费方）

**Performance Goals**: 端到端单步（截图 → 识别 → 动作）不超过 3 秒（OCR 首次加载除外，SC-005）；网页预览 5–10 fps

**Constraints**:
- 后台取图与后台输入不得激活目标、不得抢占焦点与鼠标位置（SC-002）
- 同一脚本在同一目标连续运行 10 次结果一致、坐标零偏差（SC-003）
- 坐标统一为目标客户区逻辑像素，图像坐标与点击坐标天然同一（D7）
- 不引入 Node/前端构建链，网页开箱即用
- 失败即报可读错误，禁止静默降级、兼容层与回退分支（FR-050 及项目错误处理规范）

**Scale/Scope**: 单机使用，同时管理的目标数量在十量级；脚本步骤数在百量级

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` 仍是未填写的占位模板，无已生效的项目级原则，故以项目实际生效的强制规范（`.codebuddy/rules/`，全部 `alwaysApply: true`）作为门禁依据。

| 规范 | 门禁要求 | 本方案 | 结论 |
|---|---|---|---|
| general-02 重构规范 | 未获明确要求不得加兼容/降级/fallback | D1 直接替换；OCR 指定通道不可用即报错不回退；取图路径不可用时报错不回退 | PASS |
| general-05 错误处理 | 禁裸捕获、失败即报错、报错带上下文 | FR-004/FR-019/FR-024 均要求可读错误；错误码契约见 `contracts/cli.md` | PASS |
| general-03 文档规范 | 非必要不新增文档，优先合入根目录 README | FR-045/FR-051 的说明文档落在根目录 `README.md`；本轮新增文档仅限 spec-kit 强制产物 | PASS（注：README.md 当前不存在，实施阶段需一并创建） |
| python-02 模块结构 | `__init__.py` 最小化、完整路径导入 | D10 保持扁平 + 单一 `web/` 子包，包初始化文件不重导出 | PASS |
| general-01 代码风格 | 文件头/函数头注释、命名约定、不过度封装 | 新模块 snake_case 命名并带调用链注释；不引入配置框架与多余抽象层 | PASS |
| python-01 环境 | 使用 conda `python313` | 全部候选依赖已按 cp313 实测可安装（见 research.md 第 0 节） | PASS |
| general-04 测试规范 | 不主动生成单测 | 本轮不产出测试代码，验证走 `quickstart.md` | PASS |

**偏离既有归档决策（需知悉）**：归档 change `2026-05-14-refactor-to-skill-standards` 的 design 中记录过「保持现有 7 个模块边界、不拆分也不合并」与「不引入新依赖」。这两条是**那次重构**的范围约束，而非项目级长期禁令；本次为新增能力的破坏性重构（D1 已获明确授权），必然突破该范围。见 Complexity Tracking。

**Phase 1 后复检**：新增的设计产物（`data-model.md`、`contracts/`）均不含兼容层或降级分支；数据模型中的失败策略（`on_fail`）是使用者显式配置的脚本语义，不是系统自动兜底；Web 契约的错误码均要求给出缺失前置条件的具体说明。门禁仍为 PASS。

## Project Structure

### Documentation (this feature)

```text
specs/001-auto-control-platform/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── library-api.md
│   ├── cli.md
│   └── web-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
auto_control_script/
├── __init__.py          # 保持最小化，不重导出
├── case.py              # 上层用例基类（原 game_case.py）
├── cli.py               # 命令行解析与各子命令
├── __main__.py          # python -m auto_control_script 入口
├── core/                # 公共底座：各能力包共享的依赖
│   ├── settings.py      # 配置与默认值（不得命名为 config.py：根目录 .gitignore 忽略该文件）
│   ├── errors.py        # 异常分层
│   ├── frame.py         # Frame 定义 + 画面有效性校验
│   ├── target.py        # Target 抽象 + 窗口/设备枚举与解析
│   ├── window_manager.py# 窗口句柄、矩形、DPI、客户区尺寸、置顶（由 win_handle.py 重构）
│   └── logger.py        # 日志（原 my_log.py）
├── capture/             # 截图能力
│   ├── base.py          # BaseCapture 抽象基类
│   ├── factory.py       # create_capture + capture / capture_region / save / release 入口
│   ├── window_capture.py# Windows 取图：WGC / PrintWindow / BitBlt + 客户区裁剪
│   └── adb_capture.py   # ADB 取图（exec-out screencap）
├── interaction/         # 输入能力
│   ├── base.py          # Action 定义 + BaseInteraction 抽象基类（模板方法）
│   ├── factory.py       # create_interaction + perform 入口
│   ├── win_background.py# 后台窗口消息投递
│   ├── win_foreground.py# 前台扫描码级键鼠 + 剪贴板中文输入
│   ├── adb_input.py     # ADB 输入：tap / swipe / text / keyevent
│   └── key_codes.py     # 按键名与键码映射
├── ocr/                 # OCR 能力
│   ├── base.py          # TextItem / OcrResult / BaseOcr 抽象基类
│   ├── factory.py       # create_ocr / select_engine + recognize / recognize_region 入口
│   ├── builtin_ocr.py   # 系统内置通道
│   ├── precise_ocr.py   # 高精度通道（onnxruntime 推理）
│   └── utils.py         # 语言解析等公共工具
├── matcher/             # 查找能力
│   ├── base.py          # MatchResult 数据契约
│   ├── factory.py       # find_by_image / find_by_text 入口
│   ├── image_matcher.py # 模板匹配（由 find_pic.py 重构）
│   └── text_matcher.py  # 按字查找
├── script/              # 脚本编排
│   ├── model.py         # Script / Step / RunSession / StepRecord 模型与 JSON 序列化
│   └── runner.py        # 执行引擎：步骤调度、运行控制、快照与记录
├── utils/               # 系统工具
│   ├── adb.py           # adb 命令行封装（原 adb_utils.py）
│   ├── system_cmd.py    # 保留
│   └── registry_ext.py  # 保留
└── web/
    ├── __init__.py      # 最小化
    ├── app.py           # FastAPI 应用、REST 接口、SSE 事件流、静态资源挂载
    └── static/          # 原生 HTML/CSS/JS：目标选择、预览取点、步骤编辑、运行控制台

# 已移除（内容并入上述模块，不留兼容层）
# find_pic.py → matcher/image_matcher.py
# win_handle.py → core/window_manager.py
# adb_utils.py → utils/adb.py

README.md                 # 项目统一说明（含高精度 OCR 通道启用指引，FR-045/FR-051）
requirements.txt          # 依赖清单（与 setup.py 双写，FR-048）
setup.py                  # packages 需含各能力子包与 web 子包，并声明静态资源
```

**Structure Decision**（2026-10-12 实施时调整）：plan 阶段规划的是扁平模块；实施时改为按能力分包，组织方式参考 `game_deltaforce_factory`——每个平台相关能力包固定 `base.py`（抽象基类）+ `factory.py`（工厂入口）+ 平台实现文件，公共底座收敛到 `core/`。

调整的三条理由：

1. **平台分派有归属**：原规划中 `capture.py` / `interaction.py` / `ocr.py` 既是数据契约又是分派逻辑，还要容纳多平台实现，单文件职责过重；拆包后分派逻辑集中在 `factory.py`，新增一种实现只需加文件 + 加一条分支。
2. **依赖方向可见**：`core/` 让「能力依赖公共底座、公共底座不依赖能力」在目录上一眼可见，扁平结构下看不出。
3. **能力边界即目录边界**：`capture` / `interaction` / `ocr` / `matcher` / `script` 各自成包，定位一个能力不必扫全目录。

**工厂契约**：`create_*` 只负责按目标类型 / 通道选择实现，不做兼容回退——显式指定的通道不可用时直接抛错（沿用 D1 与 FR-050）。`__init__.py` 一律最小化，调用方用完整路径导入（`from auto_control_script.capture import factory as capture`）。平台实现在工厂函数内延迟导入，避免导入期加载 WGC / winocr 等重量依赖。

**例外**：`matcher/` 不设 `BaseMatcher` 抽象基类，只提供 `find_by_image` / `find_by_text` 两个入口——按图查找与按字查找入参与机制均不同、不可互换，强行抽基类只会得到空壳；二者的共同点由 `MatchResult` 数据契约表达。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 突破归档决策「保持 7 个模块边界、不引入新依赖」，新增 17 个模块与 8 个依赖 | 本次是新增三类能力（截图/输入/OCR）+ 脚本编排 + Web 界面的破坏性重构，既有 7 个模块无法承载；D1 已明确授权不向后兼容的一次性替换 | 硬塞进既有 7 个模块会导致单个文件混杂 Windows/安卓两套实现与多种取图路径，且无法隔离可选依赖；不做 Web 层则无法满足「让后续的人快速使用」这一核心诉求 |
| 引入 `auto_control_script/web/` 子包（打破扁平约定） | Web 层必须携带静态资源文件，扁平文件无法存放；且需与库代码隔离，避免导入 Web 时牵连桌面端依赖 | 把前端资源塞进包根目录会与 Python 模块混杂，且 `setup.py` 无法干净地声明资源打包 |
