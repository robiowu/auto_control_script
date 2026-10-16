# Research: 统一截图·输入·OCR 自动化平台

**Feature**: `specs/001-auto-control-platform/spec.md` | **Date**: 2026-10-10

本文件记录 Phase 0 的技术选型结论。所有结论均以本机环境实测为依据，不以参考项目的既有选型为准。

## 0. 环境实测基线

| 项 | 实测结果 | 影响 |
|---|---|---|
| Python 解释器 | `conda` 环境 `python313`，`3.13.13 (MSC v.1944 64 bit)` | 所有依赖必须支持 cp313，参考项目的 `numpy<2` / `paddlepaddle==2.6.2` 约束不可直接照搬 |
| 环境已装包 | 仅 `pillow 12.3.0`；`numpy` / `opencv` / `pywin32` / `pyautogui` 均未安装 | 实施前必须先按新的依赖清单初始化环境 |
| `.gitignore` | 忽略根级 `config.py` | **配置模块不得命名为 `config.py`**，否则文件不入库 |
| 参考项目依赖 | `paddleocr 2.9.1` + `paddlepaddle 2.6.2`（要求 `numpy<2`） | 与 cp313 及新版 opencv 冲突，不予沿用 |

**依赖可安装性实测**（`pip install --dry-run --no-deps --ignore-installed`，conda `python313`）：

| 包 | 解析结果 | 结论 |
|---|---|---|
| `windows-capture` | 2.0.1 | 可用（WGC 后台取图，可选依赖） |
| `winocr` | 0.0.15 | 可用（系统内置 OCR 通道） |
| `rapidocr-onnxruntime` | 1.2.3 | 可用（高精度 OCR 通道） |
| `onnxruntime` | 1.31.0 | 可用（高精度通道底座） |
| `paddlepaddle` | 3.3.1 | 技术上可装，但体积大且非必要（见 D2） |
| `fastapi` / `uvicorn` | 0.143.0 / 0.54.0 | 可用（Web 层） |
| `pywin32` | 312 | 可用（窗口、GDI、消息投递） |
| `opencv-python` | 5.0.0.93 | 可用（模板匹配、图像编解码） |
| `pydirectinput` | 1.0.4 | 可用（前台真实输入） |
| `pyperclip` | 1.11.0 | 可用（中文文本输入） |

---

## D1. Web 层技术栈

**Decision**: FastAPI（服务端）+ uvicorn（承载）+ 原生 HTML/CSS/JS 前端（无构建步骤，无 npm），首页与静态资源由服务端直接返回。

**Rationale**:
- 只引入 2 个服务端依赖，无 Node 工具链，符合"易用的自动化项目"定位——使用者 `pip install` 后即可打开网页，不需编译前端。
- 本功能的前端需求只有四类：目标选择下拉、画面 `<img>` 预览、canvas 框选取点、步骤列表编辑、运行日志流。原生 JS 完全够用，引入前端框架属于过度封装。
- FastAPI 自带接口自描述文档，可直接作为 `contracts/web-api.md` 的可执行对照。
- 服务端与自动化引擎同进程，避免跨进程传递图像与句柄。

**Alternatives considered**:

| 备选 | 否决原因 |
|---|---|
| NiceGUI / Streamlit / Gradio | 额外引入一整套 UI 框架与前端资源包（体积与依赖显著增加），且画布框选、步骤拖拽排序这类交互要迁就其组件模型，灵活性反而下降 |
| Flask + 模板 | 与 FastAPI 同为轻量方案，但缺少内置的接口自描述与数据校验，契约文档需手工维护 |
| PyQt / tkinter 桌面 GUI | 用户明确可接受 Web 页；桌面 GUI 需处理线程与 UI 主循环，且无法让他人远程打开 |
| Electron / React 前端 | 引入 Node 构建链，违背"开箱即用、零前端构建"的目标 |

---

## D2. 高精度 OCR 通道

**Decision**: 采用 **RapidOCR（onnxruntime 后端）** 作为高精度通道，模型为 PP-OCRv4 系列（det + rec + cls 三个 ONNX），随包附带、无需手工下载。

**Rationale**:
- 实测 `rapidocr-onnxruntime 1.2.3` + `onnxruntime 1.31.0` 在 cp313 下可直接安装，与 `opencv-python 5.x` / `numpy 2.x` 无版本冲突；而参考项目的 `paddlepaddle 2.6.2` 要求 `numpy<2`，与本项目将使用的新版 opencv 直接冲突。
- 识别模型与 PaddleOCR 同源（PP-OCRv4），精度相当，但运行时依赖从"深度学习框架"降为"推理引擎"，安装体积与磁盘占用下降一个数量级，首次加载更快。
- 纯 CPU 推理即可满足"端到端单步不超过 3 秒"（SC-005），无需 GPU 依赖。
- 不安装时平台仍完整可用（走内置通道），满足 D2 的"可选依赖"定位。

**Alternatives considered**:

| 备选 | 否决原因 |
|---|---|
| PaddleOCR + paddlepaddle（参考项目方案） | 安装包体积大（GB 级）、要求 `numpy<2` 与新版 opencv/numpy 冲突、cp313 需自行验证版本组合、首次加载数秒；收益仅为与参考项目保持一致 |
| EasyOCR（PyTorch） | 引入 PyTorch 运行时，体积与启动开销比 onnxruntime 更大 |
| Tesseract | 中文识别效果弱于 PP-OCR 系列，且需额外安装系统级可执行文件与语言包 |
| 云端 OCR API | 违背"离线可用"假设，且引入网络依赖与凭据管理 |

---

## D3. 系统内置 OCR 通道

**Decision**: 采用 `winocr`（封装 Windows 系统 OCR，Win10 1809+ 起可用），零模型下载、零额外体积。

**Rationale**: 满足 D2 中"不装高精度引擎也完整可用"的要求，给使用者一个开箱即用的默认通道。

**已知限制（必须在实现与文档中原样暴露，不得粉饰）**:
- 系统 OCR **不返回逐条置信度**。因此内置通道的结果中置信度字段为"不可用"标记，而非伪造一个看似正常的数值；使用者若需要按置信度过滤，必须启用高精度通道。该限制直接约束 FR-020 与 SC-009 的表达方式。
- 返回坐标为系统 OCR 自身的包围盒，需换算到统一的图像坐标系。
- 调用需在事件循环中执行（`winocr` 为异步接口），实现侧需固定复用一个事件循环，避免反复创建。

---

## D4. Windows 后台取图方式

**Decision**: 默认 **PrintWindow（PW_RENDERFULLCONTENT）+ BitBlt 回退**；**WGC（windows-capture）作为可选增强**，仅在已安装该包且目标支持时启用。

**Rationale**:
- PrintWindow/BitBlt 只依赖 `pywin32`，是零新增依赖的基线能力，绝大多数桌面窗口在遮挡状态下仍可取到合成后的内容。
- WGC 对游戏/全屏渲染类窗口兼容性最好，但依赖 `windows-capture`（Rust 扩展，2.0.1 实测可装）且 API 版本间有差异，因此定位为可选增强而非默认路径。
- 三条路径统一由工厂选择，选择结果与切换原因写入运行日志（FR-007、FR-049）。

**Alternatives considered**:

| 备选 | 否决原因 |
|---|---|
| 仅 WGC | 依赖第三方扩展包，未安装时整个截图能力不可用，违背"开箱即用" |
| Desktop Duplication | 只能抓整个桌面/显示器，无法按窗口隔离，且实现复杂度高 |
| mss / PIL ImageGrab | 抓的是屏幕合成结果，窗口被遮挡时抓到的是遮挡物，不满足 FR-006 |

**画面有效性判定（对应 FR-006「不得返回黑图/空图」）**: 取图后做一次低成本校验——全图单色、全黑、或像素方差低于阈值即判定为无效画面，直接报出可读错误并指明当前使用的取图路径，交由使用者切换方式或改用前台截图。

---

## D5. 输入能力：前台与后台

**Decision**:
- **后台**：窗口消息投递（`WM_LBUTTON*` / `WM_KEY*` / `WM_CHAR` / `WM_MOUSEWHEEL`），不激活窗口、不抢占焦点与鼠标位置。中文等非 ASCII 文本通过 `WM_CHAR` 逐字符投递或剪贴板粘贴。
- **前台**：`pydirectinput`（底层为 `SendInput` 扫描码），对全屏/游戏类窗口兼容性优于常规键鼠库；滚动用 `win32api.mouse_event`，中文输入走剪贴板粘贴。

**Rationale**: 与参考项目一致且已被实机验证；`pydirectinput` 对游戏窗口的兼容性是选择它而非常规键鼠库的关键原因。

**依赖变更**: 移除现有 `pyautogui` 依赖（前台输入改由 `pydirectinput` 承担）。依据 D1「直接替换、不留兼容层」，旧的前台点击实现不保留。

**已知限制（必须在实现与文档中原样暴露）**: 后台消息投递**无法验证动作是否真的被应用处理**——`PostMessage` 返回成功只代表消息入队。因此 FR-019 中"动作未生效"的判定以"目标失效 / 消息投递失败 / 窗口句柄无效"为准，像素级的结果校验交由脚本中的"截图比对"步骤完成，不在动作层伪造成功。

---

## D6. ADB 通道

**Decision**: 沿用子进程调用 `adb` 可执行文件的方式，不引入纯 Python 的 ADB 协议库。截图统一使用 `adb exec-out screencap -p`（避免 `shell` 模式下 stdout 换行被转换导致的 PNG 损坏），输入使用 `adb shell input tap/swipe/text/keyevent`。多设备通过 `-s <serial>` 区分。

**Rationale**: 使用者本机通常已有可用的 adb 与设备授权环境；子进程方式透明、可排障（`adb devices` 能直接看到状态），且不额外引入协议实现依赖。

**Alternatives considered**: `adbutils` 等纯 Python 实现——省去 adb 可执行文件依赖，但设备授权/端口管理等场景与官方 adb 行为存在差异，排障成本高。

---

## D7. 图像与坐标统一契约

**Decision**:
- 所有来源（Windows 三种路径、ADB）的截图统一返回 **BGR 顺序的 numpy 数组**，并附带统一的元信息对象（尺寸、来源目标、采集时间、取图路径、坐标说明）。
- 所有对外坐标统一为 **以目标客户区左上角为原点、按目标逻辑像素计量的坐标**；Windows 侧在取图阶段直接裁剪掉边框/标题栏并做 DPI 换算，使"图像坐标"与"点击坐标"天然同一。

**Rationale**: 参考项目的最大耦合坑是 WGC 截图含边框导致业务侧硬编码 `-1/-31` 偏移（其 `coord_transform.py`）。本项目在取图层就消除偏移，使后续 OCR 区域、点击坐标、脚本录制坐标无需任何换算，直接支撑 SC-003「坐标偏差为 0 像素」与 FR-010。

**Alternatives considered**: 保留含边框原图 + 在业务侧做坐标换算——被否决，因为偏移常量随窗口样式/系统版本变化，且会把复杂度扩散到 OCR、脚本、Web 取点等每一个消费者。

---

## D8. 脚本与配置持久化

**Decision**:
- 脚本以 **JSON 文件** 持久化，字段直接对应数据模型；导入导出即文件拷贝。
- 运行日志与画面快照写入用户目录（`%APPDATA%/auto_control_script/` 下的 `scripts/`、`runs/`），沿用项目既有的用户目录约定（`game_case.py` 已在用该根目录）。
- 配置模块命名为 **`settings.py`** 而非 `config.py`——根目录 `.gitignore` 忽略 `config.py`，命名为 `config.py` 会导致文件不入库。
- 不引入配置框架（如 pydantic-settings）：配置量小，用带默认值的常量模块 + 可选 JSON 配置文件即可，避免过度封装。

---

## D9. Web 实时性与并发

**Decision**:
- 画面预览：服务端按请求返回 JPEG（`image/jpeg`），前端 `<img>` 定时刷新，不做长连接推流。
- 运行日志与步骤状态：**SSE（Server-Sent Events）单向推送**。
- 多目标并发：每个目标绑定独立的执行器实例，运行在不同的工作线程上；Web 服务主线程只负责接口与状态查询。

**Rationale**: 预览只需 5–10 fps，定时刷新比流媒体实现简单一个数量级；运行态是典型的"服务端→浏览器"单向流，SSE 比 WebSocket 更贴合且无需额外依赖。

**Alternatives considered**: WebSocket（双向，但本项目浏览器端只订阅不发送控制指令，控制走普通 HTTP 即可）；轮询日志（实现最简单但运行面板会有可见延迟，不满足 FR-041）。

---

## D10. 模块组织与打包

**Decision**: 源码保持**扁平模块**（与项目既有 7 个模块平级），仅 Web 层使用 `auto_control_script/web/` 一个子包存放服务端与静态资源。

**Rationale**: 项目的既定约定是"扁平模块、完整路径导入、`__init__.py` 最小化"；Web 层因含静态资源必须单独成目录，故破例一次。

**打包影响（必须同步处理）**: `setup.py` 的 `packages` 是显式列表 `['auto_control_script']`，新增子包后必须改为 `['auto_control_script', 'auto_control_script.web']`，并通过 `package_data` / `MANIFEST.in` 把 `web/static/` 下的前端资源打进包，否则 `pip install .` 后网页打不开。依赖清单需在 `setup.py` 与 `requirements.txt` 两处同步（FR-048）。

---

## 待确认项收敛结果

规格中原有的 2 项 NEEDS CLARIFICATION 已由使用者决策（D1 不向后兼容、D2/D3 OCR 双通道 + 文档指引），本轮研究无新增待确认项。技术规格中的全部选型已在本文件给出结论，无遗留 `NEEDS CLARIFICATION`。
