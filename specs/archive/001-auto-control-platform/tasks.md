# Tasks: 统一截图·输入·OCR 自动化平台

> **归档状态（2026-10-16）**：本需求已实施完成，归档至 `specs/archive/001-auto-control-platform/`。
> 52 条功能需求全部落地——44 条原本已实现，8 条在归档前的核对中补齐并实测（详见文末「FR 核对结论」）。
> 仍待人工的验收项：T047 剩「Web 拖拽选区与运行控制」「传统窗口后台输入实际生效」两项；
> SC-001 与 SC-008 需真人按文档实操。逐条完成后方可勾选 T047。

**Input**: Design documents from `/specs/001-auto-control-platform/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: 本次不生成测试任务。规格未要求测试，且项目规范约定「不主动生成单测」；每个用户故事的验收以 `quickstart.md` 中的端到端场景为准，实现完成后按场景逐条跑通即可。

**Organization**: 任务按用户故事分组，每个故事可独立实现、独立验证、独立交付。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（改动不同文件，且不依赖未完成任务）
- **[Story]**: 任务归属的用户故事（US1~US5）
- 描述中均给出确切文件路径

## Path Conventions

本项目为单包库 + CLI + Web（同一进程），源码位于仓库根目录下的 `auto_control_script/`，前端资源位于 `auto_control_script/web/static/`，不建前端构建链。

**2026-10-12 结构调整**：实施时由「扁平模块」改为按能力分包（组织方式参考 `game_deltaforce_factory`），每个平台相关能力包固定 `base.py`（抽象基类）+ `factory.py`（工厂入口）+ 平台实现文件。本文件 T001~T048 给出的路径按下表对照，路径变化不影响任务本身的完成判定：

| 任务中的路径 | 实际路径 |
|---|---|
| `settings.py` / `errors.py` / `frame.py` / `target.py` / `window_manager.py` | `core/` 下同名文件 |
| `my_log.py` | `core/logger.py` |
| `capture.py`（Frame 与取图工厂） | `core/frame.py` + `capture/factory.py` |
| `capture_win.py` / `capture_adb.py` | `capture/window_capture.py` / `capture/adb_capture.py` |
| `interaction.py` | `interaction/base.py` + `interaction/factory.py` |
| `input_win.py` | `interaction/win_background.py`（后台）+ `interaction/win_foreground.py`（前台） |
| `input_adb.py` | `interaction/adb_input.py` |
| `ocr.py` / `ocr_builtin.py` / `ocr_precise.py` | `ocr/factory.py` + `ocr/base.py` / `ocr/builtin_ocr.py` / `ocr/precise_ocr.py` |
| `matcher.py` | `matcher/base.py` + `matcher/factory.py` + `matcher/image_matcher.py` + `matcher/text_matcher.py` |
| `script_model.py` / `runner.py` | `script/model.py` / `script/runner.py` |
| `game_case.py` | `case.py` |
| `adb_utils.py` | `utils/adb.py` |

**回填口径**：`- [x]` 表示代码已实现且可用；未勾选的项在行下以「缺口（2026-10-12 代码核实）」标注具体缺失子项，或以「待确认」标注需实跑才能判定的项。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 依赖、打包与配置基础设施就位

- [x] T001 更新 `requirements.txt`：写入保留依赖（`pywin32`、`opencv-python`、`pillow`、`numpy`）与新增依赖（`pydirectinput`、`pyperclip`、`winocr`、`rapidocr-onnxruntime`、`onnxruntime`、`windows-capture`、`fastapi`、`uvicorn`），并移除 `pyautogui`；用注释标出 `windows-capture` 与 `rapidocr-onnxruntime` 为可选依赖
- [x] T002 更新 `setup.py`：`packages` 改为 `['auto_control_script', 'auto_control_script.web']`，通过 `package_data`/`MANIFEST.in` 声明 `web/static/` 静态资源，`install_requires` 与 `requirements.txt` 对齐（FR-048）
- [x] T003 [P] 创建 `auto_control_script/settings.py`：集中存放默认配置与可选 JSON 覆盖；**文件名必须为 `settings.py`**，根目录 `.gitignore` 忽略 `config.py`，命名为 `config.py` 会导致文件不入库
- [x] T004 在 conda 环境 `python313` 下执行 `conda run -n python313 pip install -r requirements.txt`，并逐个验证 `pywin32`、`cv2`、`winocr`、`onnxruntime`、`fastapi`、`pydirectinput` 可导入（当前环境仅有 pillow，必须补装）
  - 已验证（2026-10-12）：依赖均已安装，无需补装——cv2 5.0.0.93、numpy 2.5.3、pillow 12.3.0、pywin32 312、pydirectinput 1.0.4、pyperclip 1.11.0、winocr 0.0.15、fastapi 0.143.0、uvicorn 0.54.0、onnxruntime 1.31.0，逐项 import 全部通过
  - 实测约束：`winocr` 先于 `onnxruntime` 加载会使进程直接崩溃（无异常、无输出），反向顺序正常；故 OCR 工厂必须先构造高精度通道再构造内置通道，`ocr/factory.py` 中的加载顺序不可调换

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共同依赖的核心：目标抽象、窗口管理、统一画面对象、Windows 取图、输入动作定义

**⚠️ CRITICAL**: 本阶段未完成前，任何用户故事都不得开工

- [x] T005 [P] 创建 `auto_control_script/target.py`：`Target` 抽象（kind/id/name/width/height/available/meta）、`list_targets(kind)` 枚举窗口与设备、`resolve_target(selector)` 解析目标；解析不到即抛带上下文的错误，不返回空目标（FR-001~FR-004）
- [x] T006 [P] 创建 `auto_control_script/window_manager.py`：由 `win_handle.py` 重构而来，提供窗口枚举、句柄查找、窗口与客户区矩形、`GetDpiForWindow` 缩放换算、客户区尺寸、置顶；每次取图前刷新尺寸（FR-010、SC-003）
- [x] T007 [P] 创建 `auto_control_script/capture.py`：`Frame` 定义（BGR 像素数组 + 宽高 + 来源目标 + 采集时间 + 取图路径 + 坐标原点说明）、画面有效性校验（全黑/单色/方差过低即报可读错误并指明取图路径）、取图工厂（FR-006~FR-011）
- [x] T008 创建 `auto_control_script/capture_win.py`：实现 WGC / PrintWindow(PW_RENDERFULLCONTENT) / BitBlt 三条取图路径，统一裁剪为客户区并完成 DPI 换算，提供显式资源释放；路径不可用时报错说明原因，不静默回退（依赖 T006、T007）
- [x] T009 [P] 创建 `auto_control_script/interaction.py`：`Action` 定义（kind/point/end_point/text/mode/wait_before/jitter/retry）与输入工厂，负责后台/前台模式分派与目标失效判定（FR-014~FR-019）
- [x] T010 [P] 初始化用户目录结构：`%APPDATA%/auto_control_script/` 下建立 `scripts/`、`runs/`、`logs/`，并接入既有 `auto_control_script/my_log.py` 输出运行日志（沿用 `game_case.py` 已有的用户目录约定）

---

## Phase 3: User Story 1 (P1) — 以工具函数/CLI 方式调用三大能力

**Goal**: 开发者在自己的 Python 脚本或命令行中，指定一个目标即可完成「截图 → 识别 → 输入」闭环；Windows 与安卓两侧坐标语义一致。

**Independent Test**: 按 `quickstart.md` 第 1~6 节执行：枚举目标 → 遮挡状态下后台截图 → OCR（含指定高精度通道报错）→ 后台点击与中文输入 → 目标关闭时报退出码 3 → 按图/按字查找的命中与不命中。全部通过即本故事完成，无需 Web 界面。

### 实现任务

- [x] T011 [P] [US1] 创建 `auto_control_script/input_win.py`：后台窗口消息投递实现，覆盖单击/双击/右键/移动/拖拽/滚轮/单键/组合键/文本输入（中文经剪贴板或逐字符投递）；坐标越界报出目标实际尺寸，目标失效或投递失败报可读错误（FR-012、FR-014~FR-019，D5）
- [x] T012 [P] [US1] 创建 `auto_control_script/capture_adb.py`：以 `adb exec-out screencap -p` 取图，做 PNG 头尾校验，产出与 Windows 侧一致的 `Frame`（FR-008、D6）
- [x] T013 [US1] 创建 `auto_control_script/input_adb.py`：经 `adb shell input` 下发 tap / swipe / 长按 / text / keyevent（依赖 T005 的设备目标解析）
  - 原缺口（已于 2026-10-12 补齐）：缺「长按」——`ACTION_KINDS` 中无 long_press，adb 侧只有 tap / swipe / text / keyevent
- [x] T014 [P] [US1] 创建 `auto_control_script/ocr.py`：`OcrResult`/`TextItem` 定义、双通道工厂、按阅读顺序排序、区域识别坐标回写、结构化提取（`extract` 失败返回 `None` 不猜值）（FR-020~FR-025）
- [x] T015 [P] [US1] 创建 `auto_control_script/ocr_builtin.py`：系统内置 OCR 通道；**该通道无真实置信度，`confidence` 置空并置 `confidence_available=False`，不得伪造数值**；固定复用单个事件循环（FR-023、D3）
  - 原缺口（已于 2026-10-12 补齐）：未复用单个事件循环——直接调 `winocr.recognize_pil_sync`，代码内无 asyncio 相关实现
- [x] T016 [P] [US1] 创建 `auto_control_script/ocr_precise.py`：高精度通道（onnxruntime 推理）；未安装即报出「缺少什么」的具体说明，不回退到内置通道（FR-024、D2）
- [x] T017 [US1] 创建 `auto_control_script/matcher.py`：由 `find_pic.py` 重构而来，提供模板匹配与按图/按字查找，统一返回 `MatchResult`；未命中返回 `found=False` 且不带坐标并给出原因（FR-025、FR-026）
- [x] T018 [P] [US1] 创建 `auto_control_script/script_model.py`：`Script`/`Step`/`RunSession`/`StepRecord` 模型与 JSON 序列化；加载时校验步骤引用（指向不存在或非查找类步骤即报错），坐标为固定值时记录基准分辨率（FR-027~FR-029）
  - 原缺口（已于 2026-10-12 补齐）：坐标为固定值时未自动记录基准分辨率——`base_width/base_height` 存在但 Web 端恒写 0
- [x] T019 [US1] 创建 `auto_control_script/runner.py`：步骤调度与运行控制（start/pause/resume/stop/step_once/retry_step），在步骤边界暂停、查找类步骤的超时与失败策略（中止/继续/重试）、逐步执行记录与画面快照（依赖 T018）
- [x] T020 [US1] 创建 `auto_control_script/cli.py`：`targets`/`capture`/`ocr`/`input`/`run`/`script` 六个子命令，支持 `--json` 机器可读输出与人类可读输出，错误写 stderr 并按 `contracts/cli.md` 的退出码返回（FR-042、FR-043）
- [x] T021 [US1] 创建 `auto_control_script/__main__.py`：提供 `python -m auto_control_script` 入口并转调 `cli.py`
- [x] T022 [US1] 删除 `auto_control_script/find_pic.py`、`auto_control_script/win_handle.py`、`auto_control_script/adb_utils.py` 三个旧模块（内容已分别迁入 `capture_win.py`+`matcher.py`、`window_manager.py`+`input_win.py`、`target.py`+`capture_adb.py`+`input_adb.py`）；按 D1 不留别名、兼容层与回退分支（FR-050）
- [x] T023 [US1] 改造 `auto_control_script/game_case.py`：上层用例基类改为调用新的 target/capture/interaction/matcher 接口，使其在同一次变更中完成迁移（FR-050）

---

## Phase 4: User Story 2 (P1) — 通过网页界面可视化构建自动化脚本

**Goal**: 非开发者打开本机网页即可完成「选目标 → 看预览 → 框选取点 → 编排步骤 → 保存 → 运行 → 看日志与快照」全流程。

**Independent Test**: 按 `quickstart.md` 第 7 节执行：启动网页 → 选目标出预览 → 画面上框选填入参数 → 添加 5 步并保存 → 关页面重开后脚本完整 → 运行并可暂停/继续/停止 → 越界坐标在界面给出可读错误与快照。

### 实现任务

- [x] T024 [P] [US2] 创建 `auto_control_script/web/__init__.py`（保持最小化，不重导出）与 `web/`、`web/static/` 目录骨架（D10）
- [x] T025 [US2] 创建 `auto_control_script/web/app.py`：FastAPI 应用装配、静态资源挂载、目标查询与画面预览接口（JPEG）、统一错误响应与 `contracts/web-api.md` 中的错误码（FR-034~FR-036、FR-040）
- [x] T026 [US2] 在 `auto_control_script/web/app.py` 增加 OCR 与查找接口，以及两类通道的可用状态查询（返回缺失的前置条件说明）（FR-023、FR-024、FR-040）
- [x] T027 [US2] 在 `auto_control_script/web/app.py` 增加脚本管理接口：列表、读取、新建、保存、删除、导入、导出、校验（FR-029、FR-038）
- [x] T028 [US2] 在 `auto_control_script/web/app.py` 增加运行控制接口与 SSE 事件流（`step_started`/`step_finished`/`step_failed`/`session_state`/`log`）、会话详情、历史列表与快照读取（FR-030、FR-031、FR-039、FR-041、D9）
  - 原缺口（已于 2026-10-12 补齐）：SSE 实际事件名为 step_success / step_failed / step_skipped，契约点名的 step_started / step_finished / log 未产出
- [x] T029 [P] [US2] 创建 `auto_control_script/web/static/index.html`：目标选择器、画面预览区、步骤列表区、运行控制台四大区域的页面骨架
- [x] T030 [P] [US2] 创建 `auto_control_script/web/static/style.css`：四大区域的基础样式
- [x] T031 [US2] 创建 `auto_control_script/web/static/app.js`：目标选择与切换、画面预览定时刷新、在预览上拖拽框选区域与取点并把结果填入步骤参数（FR-035、FR-036）
  - 原缺口（已于 2026-10-12 补齐）：预览无定时刷新——只有 load 与按钮触发，无 setInterval 轮询
- [x] T032 [US2] 在 `auto_control_script/web/static/app.js` 增加步骤编辑器：步骤增删改、拖拽排序、按类型渲染参数表单、引用前序步骤的查找结果作为坐标来源（FR-027、FR-028、FR-037）
  - 原缺口（已于 2026-10-12 补齐）：排序用 ↑↓ 按钮而非拖拽；参数表单为单一固定表单，未按步骤类型动态渲染
- [x] T033 [US2] 在 `auto_control_script/web/static/app.js` 增加运行控制台：SSE 订阅、逐步状态/耗时/日志/快照展示、开始/暂停/继续/停止/单步/单步重试（FR-030、FR-039、FR-041）
  - 原缺口（已于 2026-10-12 补齐）：快照未展示——只把 `record.detail` 当文本打印，未渲染 snapshot_id 对应图片
- [x] T034 [US2] 在 `auto_control_script/cli.py` 增加 `web` 子命令：启动服务、仅监听本机回环地址并打印可访问地址（FR-034）

---

## Phase 5: User Story 3 (P2) — 后台静默执行不打扰本机使用

**Goal**: 脚本运行期间不抢焦点、不置顶目标；同时提供前台输入方式供后台不生效的目标应用使用，并允许逐步指定方式。

**Independent Test**: 按 `quickstart.md` 第 4、5 节与「故事 3」要求执行：后台点击期间使用者在另一窗口持续输入不受干扰；切换前台模式时先给出「将激活目标窗口」提示；同一步骤可单独指定前后台方式。

### 实现任务

- [x] T035 [US3] 在 `auto_control_script/input_win.py` 增加前台输入实现：扫描码级键鼠点击与按键、滚轮、剪贴板中文输入，执行前给出将激活目标窗口的提示（FR-013、D5）
  - 原缺口（已于 2026-10-12 补齐）：前台执行前未给出「将激活目标窗口」的提示——直接调 `bring_to_front()`，模块内无 logger
- [x] T036 [US3] 在 `auto_control_script/interaction.py` 完成后台/前台模式分派，支持逐步指定 `mode` 且互不影响（FR-012、FR-013）
- [x] T037 [US3] 在 `auto_control_script/runner.py` 透传步骤级输入方式，并把实际使用的方式写入 `StepRecord.detail`（FR-049）
  - 原缺口（已于 2026-10-12 补齐）：仅 click 与 input_text 把 mode 写回 `StepRecord.detail`，key / drag / scroll 未回写

---

## Phase 6: User Story 4 (P2) — 多目标与安卓设备的自动化

**Goal**: 支持多个 Windows 窗口与多台安卓设备（含 USB 与网络连接）的分别绑定与并发执行，日志可按目标筛选。

**Independent Test**: `python -m auto_control_script targets --json` 列出全部窗口与设备并标明状态；为两个目标分别绑定脚本并发运行互不干扰；停止其中一个不影响另一个。

### 实现任务

- [x] T038 [P] [US4] 在 `auto_control_script/target.py` 增加设备状态刷新与连接方式（usb/tcp）、adb 状态等差异信息（FR-003）
  - 原缺口（已于 2026-10-12 补齐）：设备 `refresh()` 沿用 `target.meta` 里缓存的 state，未重新查 `adb devices`，离线/上线不会自动翻转
- [x] T039 [P] [US4] 在 `auto_control_script/capture_adb.py` 与 `auto_control_script/input_adb.py` 支持按 serial 区分多设备，保证并发取图与输入互不串台（FR-008、FR-016、D6）
- [x] T040 [US4] 在 `auto_control_script/runner.py` 增加同目标运行互斥：同一目标已有运行中的会话时抛 `TARGET_BUSY`，停止单个目标不影响其他目标
- [x] T041 [US4] 在 `auto_control_script/web/app.py` 与 `web/static/app.js` 支持多目标切换、绑定与按目标筛选运行记录（FR-035）
  - 原缺口（已于 2026-10-12 补齐）：按目标筛选运行记录未实现——`/api/runs` 无 target 过滤参数，前端也未调用该接口

---

## Phase 7: User Story 5 (P3) — 脚本沉淀、复用与移交

**Goal**: 脚本可导出并在另一环境中还原；不同分辨率目标上有明确处理；运行产生的日志与快照受保留上限约束并可清理。

**Independent Test**: 按 `quickstart.md` 第 8 节执行：脚本 validate 通过 → 导出改名后导入 → 运行复现原行为；检查 `runs/` 下日志与快照受上限约束。

### 实现任务

- [x] T042 [US5] 在 `auto_control_script/script_model.py` 增加导入导出与版本校验：版本高于当前支持时报错说明，不猜测式加载（FR-029）
- [x] T043 [US5] 在 `auto_control_script/runner.py` 增加基准分辨率换算：坐标按目标实际尺寸换算并明确提示已换算，无法换算时报清晰错误
- [x] T044 [US5] 在 `auto_control_script/runner.py` 与存储层实现日志与快照的保留上限与清理入口（最旧优先）（FR-033）

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 文档、打包与端到端验收

- [x] T045 创建根目录 `README.md`：项目定位、三类能力说明、CLI 用法、库调用示例、Web 启动方式，以及**高精度 OCR 通道启用指引**（安装步骤与依赖体积、模型获取、启用与切换、验证是否生效、模型缺失/版本冲突/首次加载慢的排查步骤）（FR-045、FR-051、SC-008）
- [x] T046 验证打包：`pip install .` 后 `auto_control_script/web` 与其静态资源均已打进包，网页可正常打开（对应 T002 与 D10）
  - 已验证（2026-10-12）：用 `pip wheel . --no-deps` 构建 wheel 后检查内容——72 个条目，`core`/`capture`/`interaction`/`ocr`/`matcher`/`script`/`utils`/`web` 八个子包与 `web/static` 下 index.html、app.js、style.css 均在包内；另启动 Web 服务验证 `/`、`/app.js`、`/style.css` 均返回 200，页面可正常打开
  - 未实际执行 `pip install .`，以免污染 python313 环境；包内容与可访问性已由 wheel 与 HTTP 双重确认
- [ ] T047 按 `quickstart.md` 的 10 组场景执行端到端验证，逐条记录结果（含安卓项在无设备时跳过）
  - 已自动验证（2026-10-12）：场景 1 目标枚举、场景 2 后台截图（7680x2160，printwindow 路径）、场景 3 OCR 双通道（自动选择命中 precise 共 38 条中文；指定 builtin 时 confidence_available=false 且置信度为空；切换通道后标识随之改变）、场景 6 按字查找（命中带坐标，未命中不带坐标且 detail 给出原因）、场景 8 脚本校验/导出/改名导入/版本校验（步骤与参数完全一致，版本 999 报可读错误）、场景 9 高精度通道（返回 channel: precise）、场景 7 的 Web 服务与静态资源、场景 10 保留上限配置（max_runs=20、max_snapshots=200）
  - 实机验证（2026-10-16，Windows 目标 594682「胜利女神：新的希望」已被其他窗口完全遮挡，安卓设备 bd289914 在线）：
    - 场景 2 遮挡验证**通过**：窗口被完全遮挡时仍取到 2436x1370 真实画面（`printwindow` 路径），OCR 读出 `WAVE 1/3`、`08:55`、`TAB`、`ESC`、`暂停`、`新手教学`、`剩余时间：08:55`；取图期间前台窗口句柄与鼠标位置均未改变
    - 场景 4 后台点击与输入**部分通过**：修复判定缺陷后退出码为 0、焦点零抢占；但对 Windows 11 新版记事本无实际输入效果（后台只投递顶层句柄，WinUI3 应用不转发到编辑子控件），已记入 README「已知环境限制」，后续在网页界面开放句柄参数
    - 场景 5 前台点击**通过**：可激活时成功激活；系统拒绝抢占焦点时返回退出码 3 与可读中文错误（修复前为未捕获异常、退出码失控为 1）
    - 安卓项**通过**：取图 1080x2400、翻页（`drag`）、OCR 定位「王者荣耀」、点击后画面变为 `TIMi` / `天美工作室群 TIMI-L1STUDIO`，游戏被真实打开
    - 场景 10 超上限清理**通过**：新增 CLI `cleanup` 后，临时把保留上限改为 2，5 条运行记录被清理为 2 条（删除最旧的 3 条），验证完毕即还原记录与配置
  - 补充修复（2026-10-16）：① `interaction/win_background.py` 的 `_post` 原用 `win32gui.PostMessage` 的返回值判定成败，而该封装成功时返回 `None`，`if not ok` 恒为真——后台点击与后台输入 100% 抛 `ActionError`，功能实际完全不可用；改用 `ctypes` 的 `PostMessageW`（返回 BOOL）判定 ② `core/window_manager.py` 的 `bring_to_front` 未捕获 `SetForegroundWindow` 抛出的 `pywintypes.error`，异常穿透到命令行顶层，退出码失控为 1（破坏「异常映射为稳定退出码」契约）；改为捕获并转 `TargetUnavailableError`
  - 补充修复（2026-10-13）：`frame.save`/`frame.load` 原先走 `cv2.imwrite`/`cv2.imread`，对含中文（非 ASCII）的路径会静默失败（`imwrite` 返回 True 却不生成文件）或报错误导（把「文件存在」报成「文件不存在或格式不支持」）；改为 `imencode` + 二进制写入 / 字节读入 + `imdecode`，并对「编码失败」与「文件不存在」分别给出可读错误，覆盖 `capture --out`、`ocr --image`、matcher 模板路径、`case` 截图保存等全部读写图入口
  - 勾选前置（剩余人工项，逐条完成后方可勾选 T047）：① 场景 7 拖拽选区/添加步骤/运行/暂停继续停止 ② 场景 4 的「文字实际进入目标窗口」待用游戏类等传统窗口补验——Windows 11 新版记事本因顶层投递限制不适用，见 README「已知环境限制」；场景 10 已用 CLI `cleanup` 验证通过，安卓项已用设备 bd289914 验证通过
- [x] T048 删除遗留 `openspec/` 目录：项目已改用 spec-kit，需求与变更统一归档在 `specs/` 下；`openspec/` 及其中的 window-capture / adb-control / game-automation / system-utils 四份旧能力描述不再维护

---

## Dependencies & Execution Order

### 阶段依赖

```text
Phase 1 Setup ──> Phase 2 Foundational ──> Phase 3 (US1) ──> Phase 4 (US2)
                                              │
                                              ├──> Phase 5 (US3)  需要 T009/T011/T019
                                              ├──> Phase 6 (US4)  需要 T005/T012/T013/T019
                                              └──> Phase 7 (US5)  需要 T018/T019
                                                        │
                                              Phase 8 Polish ──> 全部完成后
```

- **Phase 2 是硬阻塞**：T005~T010 未完成，任何故事都无从下手。
- **US1 是最早可交付的增量**：Phase 3 结束即可作为 MVP 使用（命令行 + 库）。
- **US2 依赖 US1**：Web 的所有接口都是 US1 能力的包装，且需要 `script_model.py`（T018）与 `runner.py`（T019）。
- **US3 / US4 / US5 相互独立**：三者可在 US1 完成后并行推进，互不阻塞。
- **US4 内部**：T038、T039 可并行，T040、T041 依赖前两者与 `runner.py`。
- **Phase 8 必须在全部故事完成后执行**，其中 T048 依赖 T022/T023 的模块变更结果。

### 用户故事完成顺序建议

```text
US1 (P1, MVP) → US2 (P1) → US3 (P2) / US4 (P2) 并行 → US5 (P3) → Polish
```

---

## Parallel Opportunities

### Phase 1

```text
T003 (settings.py)  ∥  T001/T002（依赖清单与打包，改动不同文件）
```

### Phase 2

```text
T005 (target.py) ∥ T006 (window_manager.py) ∥ T007 (capture.py) ∥ T009 (interaction.py) ∥ T010 (用户目录)
T008 (capture_win.py) 依赖 T006+T007，需在前两者完成后进行
```

### Phase 3 (US1)

```text
T011 (input_win.py) ∥ T012 (capture_adb.py) ∥ T014 (ocr.py) ∥ T015 (ocr_builtin.py) ∥ T016 (ocr_precise.py) ∥ T018 (script_model.py)
串行：T013 → T017 → T019 → T020 → T021 → T022 → T023
```

### Phase 4 (US2)

```text
T024 (web 骨架) ∥ T029 (index.html) ∥ T030 (style.css)
串行（同一文件）：T025 → T026 → T027 → T028；T031 → T032 → T033
T034 (cli web 子命令) 可与前端任务并行
```

### Phase 6 (US4)

```text
T038 (target.py 设备信息) ∥ T039 (adb 多设备)
```

---

## Implementation Strategy

### MVP First (仅 User Story 1)

1. 完成 Phase 1 Setup（依赖与配置）
2. 完成 Phase 2 Foundational（**硬阻塞，必须先完成**）
3. 完成 Phase 3 User Story 1（Windows 后台截图/输入 + 安卓截图/输入 + OCR 双通道 + 查找 + CLI + 库入口）
4. **停下来验证**：按 `quickstart.md` 第 1~6 节独立验收 US1
5. 此时已可作为命令行与库交付使用——这就是 MVP

### Incremental Delivery

1. Setup + Foundational → 底座就绪
2. + US1 → 命令行/库可用（MVP）
3. + US2 → 网页可视化编排可用，非开发者可上手
4. + US3 → 前台输入与逐步方式切换，覆盖后台不生效的目标应用
5. + US4 → 多窗口/多设备并发
6. + US5 → 脚本沉淀与移交
7. Polish → 文档、打包与端到端验收

每个增量都在不破坏前一增量的前提下追加价值。

### 关键提醒（实现时不得偏离）

- **禁止兼容层**：T022 删除旧模块、T023 改造 `game_case.py`，均不得保留旧命名别名或旧实现回退分支（D1、FR-050）。
- **禁止静默降级**：T008 取图路径不可用、T016 高精度通道缺失、T017 查找未命中，一律报可读错误，不回退、不凑合（general-02、general-05）。
- **置信度不得伪造**：T015 内置通道的 `confidence` 必须为空并标注 `confidence_available=False`（D3）。
- **坐标零偏移**：T008 必须在取图层完成客户区裁剪与 DPI 换算，不得把偏移留给下游（D7、SC-003）。
- **文件名陷阱**：配置模块只能是 `settings.py`，不能是 `config.py`（根目录 `.gitignore` 忽略之）。

---

## SC 验收记录（2026-10-16）

按 `spec.md` 的 Success Criteria 逐条核对。可自动化的已实测，需真人/实机的另列。

| SC | 结论 | 依据 |
|---|---|---|
| SC-001 新人 15 分钟跑通 5 步脚本 | 待人工 | 需真人按 `quickstart.md` 场景 7 实操计时 |
| SC-002 遮挡下后台截图/点击 100%、焦点零抢占 | **通过** | 2026-10-16 实机：目标 594682 被完全遮挡仍取到 2436x1370 真实画面（OCR 读出 `WAVE 1/3`、`08:55`、`暂停` 等游戏界面文字）；取图期间前台窗口句柄与鼠标位置零变化 |
| SC-003 连续 10 次一致、坐标零偏差、无泄漏 | **部分通过** | 2026-10-16 实机：连续 10 次取图+按字查找「暂停」，10/10 命中且包围盒恒定 `(1164,321,1273,385)`；「完整脚本连跑 10 次」与资源无泄漏仍待实机 |
| SC-004 中文 OCR 准确率不低于 90% | **通过 96.7%（29/30）** | `tests/benchmark/ocr_benchmark.py`；包围盒中心 29/29 落在文字区域内 |
| SC-005 端到端单步不超过 3 秒 | **OCR 部分通过** | `tests/benchmark/ocr_benchmark.py`：热态整图 1.62s、区域识别 1.26s；首帧 4.57s 含模型加载，按规格不计入 |
| SC-006 CLI 与库调用语义一致 | **通过** | `tests/benchmark/cli_lib_parity.py`：整图、区域识别、错误码（CAPTURE_FAILED）全部一致 |
| SC-007 日志与快照定位成功率不低于 90% | 待人工（**前置缺陷**） | 需构造失败脚本后由使用者判读；但 `StepRecord.snapshot_id` 在全项目从未被赋值（见下方 FR 核对结论 FR-032），快照目前无法与步骤关联，须先修复再验收 |
| SC-008 新人按文档独立完成高精度通道启用 | 待人工 | 需未接触过本项目者按 README 实操 |
| SC-009 通道标识可见且随切换改变 | **通过** | T047 场景 3（自动选择命中 precise；指定 builtin 时标识随之改变） |

**基准口径**：SC-004/SC-005 的基准图为合成渲染的清晰中文文字（微软雅黑 32 号，30 条界面常见词汇），非真实界面截图；真实界面图上的准确率需人工实机补测。

---

## FR 核对结论（2026-10-16，归档前）

逐条比对 `spec.md` 的 52 条功能需求（FR-001~FR-052，无 NFR 编号条目）与 `auto_control_script/` 下的实现：**44 条已完整落地，8 条为部分实现，0 条未实现**。三大底座（Windows/Android 截图、后台+前台输入、双通道 OCR）与脚本引擎、CLI、Web 界面均有实打实的代码对应；FR-050「不留兼容层」经 grep 验证代码中零命中别名/回退分支。

| FR | 要求 | 差在哪 |
|---|---|---|
| FR-002 | 窗口枚举标出可见性 | `Target` 无 `visible` 字段，`meta` 只有类名与客户区尺寸，调用方拿不到「是否可见」 |
| FR-005 | 截图覆盖整屏/窗口/区域 | **缺整屏（桌面）取图路径**：`Target.kind` 仅 `window`/`device`，四条取图路径均以 HWND 为输入，无桌面 DC 取图 |
| FR-032 | 逐步日志与关键步骤快照 | **`StepRecord.snapshot_id` 从未赋值**（`runner` 只写 `detail["snapshot"]`），且仅 `capture` 类步骤存快照，查找类步骤不存 |
| FR-034 | 日志快照保留上限与清理入口 | 上限配置与自动清理有（CLI `run` 结束触发一次），但无独立的 CLI/Web 清理入口，快照满后直接不存 |
| FR-037 | 预览框选/取点填入步骤参数 | 结果只写进页面底部独立展示框，与步骤表单的 `step-point`/`step-region` 无赋值关联，需手工抄录 |
| FR-039 | 脚本导入 | 后端有 `POST /api/scripts/import`，网页无导入按钮与文件选择控件 |
| FR-040 | 运行控制台显示画面快照 | 因 FR-032，`if (record.snapshot_id)` 分支永不触发；快照 HTTP 路由存在但无调用方 |
| FR-047 | 能力包固定 `base.py` + `factory.py` | `script/` 包只有 `model.py`/`runner.py`，是唯一未配齐两件套的能力包 |

**与既有记录冲突的一处**：本文第 118 行把「快照未展示」记为「原缺口，已于 2026-10-12 补齐」，但当时只补了前端读取侧，后端赋值侧（`StepRecord.snapshot_id`）仍缺失，故该条实际**未完成**，不应视为已补齐——FR-032/FR-040 即由此而来。

### 修复情况（2026-10-16 同日，8 条已全部修复并实测）

| FR | 修复内容 | 实测 |
|---|---|---|
| FR-002 | `Target` 增加 `visible` 字段；CLI `targets` 与网页目标列表均输出 | `targets --json` 输出 `"visible": true` |
| FR-005 | 新增整屏目标 `desktop`：`core/target.py` 的 `build_desktop_target()` 与 `capture/desktop_capture.py`（虚拟屏幕 GDI 拷贝） | 取到虚拟屏幕 5120x1440，原点 `(-2560,0)` 的负坐标正确处理 |
| FR-032 / FR-040 | 查找类步骤命中与失败时均保存快照，`_execute_index` 把 `detail["snapshot"]` 写入 `StepRecord.snapshot_id` | 单步脚本运行后 `snapshot_id='000'`（修复前恒为 `None`） |
| FR-034 | 新增 CLI `cleanup` 子命令与网页 `POST /api/runs/cleanup` | `cleanup` 输出「删除 0 条，保留上限=20 条」 |
| FR-037 | 预览框选/取点结果自动填入步骤表单的 `step-point` / `step-region` | 前端改动，待人工在网页上确认 |
| FR-039 | 网页脚本区新增「导入」按钮，接后端已有的 `/api/scripts/import` | 前端改动，待人工在网页上确认 |
| FR-047 | 新增 `script/base.py`（`BaseRunner`）与 `script/factory.py`（`create_runner`）；`Runner` 继承 `BaseRunner`，CLI 与网页改由工厂创建 | 工厂返回 `Runner`，`isinstance(BaseRunner)=True` |
