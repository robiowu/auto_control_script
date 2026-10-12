# Data Model: 统一截图·输入·OCR 自动化平台

**Feature**: `specs/001-auto-control-platform/spec.md` | **Date**: 2026-10-10

数据模型分两层：**运行时对象**（进程内流转，含像素等不可序列化数据）与**持久化对象**（落 JSON 文件，可导入导出）。两者通过显式的转换入口衔接，不使用隐式序列化。

## 1. 实体总览

| 实体 | 类别 | 说明 |
|---|---|---|
| `Target` | 运行时 + 可寻址标识 | 一个 Windows 窗口或一台安卓设备 |
| `Frame` | 运行时 | 一次截图的结果（像素 + 元信息） |
| `TextItem` | 持久化 | OCR 输出的一条文字 |
| `OcrResult` | 运行时 | 一次 OCR 调用的整体结果与通道信息 |
| `MatchResult` | 运行时 | 一次查找（按图 / 按字）的结果 |
| `Action` | 运行时 | 一次输入动作的规格 |
| `Step` | 持久化 | 脚本中的一个步骤 |
| `Script` | 持久化 | 一段可保存、可复用的自动化流程 |
| `RunSession` | 运行时 + 落盘摘要 | 一次脚本执行过程 |
| `StepRecord` | 持久化 | 一次运行中单个步骤的执行记录 |

## 2. Target（目标）

统一寻址 Windows 窗口与安卓设备，是所有能力的第一参数。

| 字段 | 类型 | 说明与校验 |
|---|---|---|
| `kind` | 枚举 `window` / `device` | 决定可用的取图与输入方式 |
| `id` | str | 稳定标识：窗口为句柄数值串，设备为 adb serial。同一目标在多次枚举间保持稳定 |
| `name` | str | 人类可读名称：窗口标题 / 设备型号或 serial |
| `width` `height` | int | **客户区**逻辑像素尺寸（窗口不含边框；设备为物理分辨率） |
| `available` | bool | 句柄有效 / 设备在线 |
| `meta` | dict | 差异信息：窗口的进程、类名；设备的连接方式（usb / tcp）、adb 状态 |

**校验规则**
- 构造时必须能解析出 `id`；解析失败即报错并说明"找不到窗口/设备"，不返回空目标（FR-004）。
- `available == false` 的目标不得用于取图或输入，调用时立即报出可读错误（FR-004、FR-019）。
- 窗口目标的 `width/height` 必须在每次取图前刷新，窗口被缩放/移动后坐标仍然正确（FR-010、SC-003）。

**关系**：一个 `Target` 产出多个 `Frame`；一个 `Target` 同时最多绑定一个运行中的 `RunSession`（FR 边界情况：避免两个脚本穿插操作同一目标）。

## 3. Frame（画面帧）

所有来源截图的统一产物，也是 OCR 与模板匹配的唯一图像输入。

| 字段 | 类型 | 说明与校验 |
|---|---|---|
| `pixels` | 像素数组 | **BGR 顺序**，形状 `(height, width, 3)`，无符号 8 位 |
| `width` `height` | int | 与 `pixels` 形状一致 |
| `target_id` | str | 来源目标 |
| `captured_at` | 时间戳 | 采集时刻 |
| `path` | 枚举 | 实际使用的取图方式（如 `wgc` / `printwindow` / `bitblt` / `adb`），写入运行日志（FR-049） |
| `origin` | 常量说明 | 坐标原点语义：恒为"目标客户区左上角"（D7） |

**校验规则**
- `pixels` 形状必须是三维三通道；尺寸为 0 直接报错。
- **画面有效性校验**：全黑、单色、或像素方差低于阈值判定为无效画面，报出可读错误并指明 `path`，不得把无效画面交给识别（FR-006）。
- 坐标一律以 `origin` 为准，`Frame` 本身不携带任何边框偏移量（D7：偏移在取图层已消除）。

**关系**：一次 `Frame` 可被多次 OCR / 模板匹配复用；`RunSession` 的快照由 `Frame` 编码后落盘。

## 4. TextItem / OcrResult（OCR 输出）

| 字段（TextItem） | 类型 | 说明 |
|---|---|---|
| `text` | str | 识别出的文字 |
| `box` | 四元组 int | 包围盒 `(x1, y1, x2, y2)`，相对输入图像的绝对坐标（区域识别时回写为原图坐标，FR-021） |
| `confidence` | float 或 `None` | 置信度；**内置通道不提供置信度，取值为 `None` 并在 `OcrResult` 中标注原因**（D3） |
| `order` | int | 阅读顺序序号（从上到下、从左到右） |

| 字段（OcrResult） | 类型 | 说明 |
|---|---|---|
| `items` | TextItem 列表 | 按 `order` 排序 |
| `channel` | 枚举 `builtin` / `precise` | **本次实际使用的通道**，写入日志并在界面展示（FR-023、SC-009） |
| `channel_reason` | str | 为何选该通道（自动选择命中 / 使用者显式指定 / 指定通道不可用） |
| `confidence_available` | bool | 该通道是否提供真实置信度 |
| `language` | str | 识别语言（FR-022） |
| `region` | 四元组 int 或 `None` | 识别区域；`None` 表示整图 |

**校验规则**
- `region` 越界即报错，不静默裁剪。
- 指定通道不可用时报出"缺少什么"的具体说明（FR-024），不回退到另一个通道后当作无事发生（D2/降级禁令）。
- 结构化提取（数字/金额/时间/百分比）失败返回空结果，不返回猜测值（FR-025）。

## 5. MatchResult（查找结果）

按图（模板匹配）与按字（OCR 定位）两种查找的统一产物。

| 字段 | 类型 | 说明 |
|---|---|---|
| `found` | bool | 是否命中 |
| `kind` | 枚举 `image` / `text` | 查找方式 |
| `point` | 二元组 int 或 `None` | 可直接用于点击的中心坐标 |
| `box` | 四元组 int 或 `None` | 命中区域，可直接用于区域识别 |
| `score` | float | 匹配置信度；按字查找时取对应 `TextItem.confidence`，不可用时为 `None` |
| `detail` | str | 未命中时的原因说明（超时、未找到、画面无效等） |

**校验规则**：未命中必须返回明确的 `found=False` 且不给出坐标（FR-026）；`score` 低于脚本设定阈值时按步骤的失败策略处理（FR-032），不做"取最高分凑合"的兜底。

## 6. Action（动作）

| 字段 | 类型 | 说明 |
|---|---|---|
| `kind` | 枚举 | `click` / `double_click` / `right_click` / `move` / `drag` / `scroll` / `key` / `hotkey` / `input_text` |
| `point` | 二元组 int | 目标客户区坐标（拖拽为起点，配合 `end_point`） |
| `end_point` | 二元组 int 或 `None` | 拖拽终点 |
| `text` | str 或 `None` | 输入文本或按键名 |
| `mode` | 枚举 `background` / `foreground` | 后台（不抢焦点）或前台（真实键鼠）（FR-012、FR-013） |
| `wait_before` | float | 动作前等待秒数 |
| `jitter` | float | 随机抖动幅度（FR-018） |
| `retry` | int | 失败重试次数与间隔（FR-018） |

**校验规则**：坐标超出目标客户区范围即报错并给出目标实际尺寸（FR-017）；前台模式执行前必须给出"将激活目标窗口"的提示（FR-013）；目标不可用或消息投递失败即报出可读错误，不静默继续（FR-019）。

## 7. Step（步骤）与 Script（脚本）

`Step` 为持久化单元，`Script` 为其有序集合。

| Step 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 步骤唯一标识，供后续步骤引用其结果（FR-028） |
| `type` | 枚举 | 等待 / 截图 / 按图查找 / 按字查找 / 点击 / 输入文本 / 按键 / 拖拽 / 滚动 / 条件判断 / 循环 / 记录日志（FR-027） |
| `enabled` | bool | 是否参与运行 |
| `params` | dict | 类型相关参数：坐标或区域、文本、模板引用、超时、失败策略 |
| `ref` | str 或 `None` | 引用的前序步骤 `id`，表示坐标来源于该步骤的查找结果（FR-028） |
| `on_fail` | 枚举 | 失败策略：中止 / 继续 / 重试（FR-032） |
| `timeout` | float | 查找类步骤的超时 |
| `note` | str | 备注 |

| Script 字段 | 类型 | 说明 |
|---|---|---|
| `name` | str | 脚本名 |
| `version` | int | 模型版本，导入时用于兼容性判定 |
| `base_width` `base_height` | int | 基准分辨率；在分辨率不同的目标上运行时按实际尺寸换算并明确提示（FR 边界情况） |
| `target_kind` | 枚举 | 该脚本适用的目标类型 |
| `steps` | Step 列表 | 有序步骤序列 |
| `options` | dict | 全局运行配置：默认输入方式、默认超时、快照保留策略 |

**校验规则**
- 引用 `ref` 指向不存在的步骤 id、或指向非查找类步骤，加载脚本时即报错。
- `ref` 的目标步骤未命中时，按该步骤自身的失败策略处理，不回退到硬编码坐标。
- 导入的脚本 `version` 高于当前支持版本时报错并说明，不猜测式加载。
- 坐标为固定值的步骤在不同分辨率目标上运行时必须换算并提示；无法换算时报清晰错误。

**持久化**：JSON 文件，一份脚本一个文件；导入导出即文件拷贝（FR-029）。

## 8. RunSession（运行会话）与 StepRecord（执行记录）

| RunSession 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 运行标识 |
| `script_name` | str | 脚本名 |
| `target_id` | str | 绑定目标 |
| `state` | 枚举 | `idle` / `running` / `paused` / `stopped` / `succeeded` / `failed` |
| `current_step_index` | int | 当前执行到的步骤序号 |
| `started_at` `finished_at` | 时间戳或 `None` | 起止时间 |
| `records` | StepRecord 列表 | 逐步执行记录（FR-031） |
| `snapshots` | 快照引用列表 | 关键步骤的画面快照（FR-031、FR-033） |

| StepRecord 字段 | 类型 | 说明 |
|---|---|---|
| `step_id` `index` | str / int | 步骤标识与序号 |
| `status` | 枚举 | `pending` / `running` / `success` / `failed` / `skipped` |
| `duration` | float | 耗时 |
| `snapshot_id` | str 或 `None` | 关联快照 |
| `error` | str 或 `None` | **可读的失败原因**（FR-031、SC-007） |
| `detail` | dict | 关键决策信息：使用的取图路径、输入方式、OCR 通道（FR-049） |

**状态流转**

```text
idle ──start──> running ──pause──> paused ──resume──> running
                  │                   │
                  ├──stop─────────────┴──> stopped
                  ├──step failed (on_fail=abort)──> failed
                  └──all steps done──> succeeded
```

- 暂停/继续只在步骤边界生效，不在单个动作中途挂起（对应 FR-030 与用户故事 2 的验收）。
- `stopped` 为使用者主动终止，必须记录终止原因与终止时所在步骤。
- 单步执行与单步重试：以 `current_step_index` 为游标，由使用者或调试入口驱动（FR-030）。

**校验规则**
- 同一 `Target` 上不允许同时存在两个 `running` 会话（边界情况：避免动作穿插）。
- 日志与快照数量超过保留上限时按最旧优先清理（FR-033）。
- Web 页面关闭或断连不终止运行中的会话；重新打开页面可按 `id` 查看历史记录与快照（边界情况）。

## 9. 存储布局

```text
%APPDATA%/auto_control_script/
├── settings.json         # 可选配置覆盖（默认值内置于代码）
├── scripts/*.json        # 脚本（FR-029）
├── runs/<session_id>/    # 运行日志、快照（FR-031、FR-033）
└── logs/                 # 运行日志（沿用既有日志目录约定）
```

脚本与运行数据使用用户目录而非安装目录，保证以库形式安装后仍可读写。
