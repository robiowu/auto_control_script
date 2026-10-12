# Library API Contract: 统一截图·输入·OCR 自动化平台

**Feature**: `specs/001-auto-control-platform/spec.md` | **Date**: 2026-10-10

本契约描述以库方式被导入调用时的对外接口（FR-044）。所有符号使用**完整路径导入**（项目既有约定），包初始化文件不重导出。

> 2026-10-12 更新：源码由扁平模块改为按能力分包（`core/` `capture/` `interaction/` `ocr/` `matcher/` `script/` `utils/`），下方导入路径同步为实际路径；函数签名与返回结构未变。

## 1. 约定

- 坐标：二元组 `(x, y)`，单位为目标客户区逻辑像素，原点为客户区左上角；区域为四元组 `(x1, y1, x2, y2)`。
- 图像：BGR 顺序的像素数组，见 `data-model.md` 的 `Frame`。
- 失败：一律抛出带上下文的异常（目标标识、实际尺寸、取图路径、通道名等），不做静默降级、不返回空值代替失败。
- 通道：OCR 与取图方式均可通过参数显式指定；省略时自动选择，并在返回值中给出实际使用的通道（FR-023、FR-007）。

## 2. 目标

```python
from auto_control_script.core.target import list_targets, resolve_target

list_targets(kind: str = "all") -> list[dict]
# 返回可枚举的目标清单：kind/id/name/width/height/available/meta（FR-002、FR-003）

resolve_target(selector: str) -> Target
# 按 id 或名称解析出目标；解析不到即抛错（FR-001、FR-004）
```

## 3. 截图

```python
from auto_control_script.capture.factory import capture, capture_region

capture(target: Target, path: str = "auto") -> Frame
# path: "auto" | "wgc" | "printwindow" | "bitblt" | "adb"（FR-005~FR-009）

capture_region(target: Target, region: tuple[int,int,int,int], path: str = "auto") -> Frame
```

- 窗口被遮挡时取到窗口内容而非遮挡物（FR-006）；取不到即报错，不返回黑图。
- `Frame` 已裁剪为客户区并完成 DPI 换算，坐标可直接用于点击（FR-010、D7）。
- 显式指定 `path` 但该路径不可用时报错说明缺少什么，不回退（FR-007、降级禁令）。
- 高频取图需配合显式的资源释放入口，避免句柄泄漏（FR-011）。

## 4. 输入

```python
from auto_control_script.interaction.factory import perform

perform(target: Target, action: Action, mode: str = "background") -> None
# mode: "background"（不激活目标）| "foreground"（真实键鼠，会激活目标）
```

`Action` 覆盖：单击、双击、右键、移动、拖拽、滚轮、单键、组合键、文本输入（FR-014～FR-016）。
支持 `wait_before`、`jitter`、`retry`（FR-018）。
动作以"目标失效 / 投递失败"判定失败并抛出可读错误（FR-019、D5）。

## 5. OCR

```python
from auto_control_script.ocr.factory import recognize, recognize_region
from auto_control_script.ocr.utils import extract

recognize(image: Frame, lang: str = "ch", channel: str = "auto") -> OcrResult
recognize_region(image: Frame, region: tuple[int,int,int,int], lang: str = "ch",
                 channel: str = "auto") -> OcrResult
# channel: "auto" | "builtin" | "precise"（FR-020~FR-024）

extract(text: str, kind: str) -> object | None
# kind: number | amount | time | percentage；无法提取返回 None，不猜值（FR-025）
```

- `OcrResult.channel` 标明实际使用的通道，`confidence_available` 标明置信度是否真实（D3、SC-009）。
- 指定 `channel="precise"` 而高精度通道未安装时，抛出说明"缺少什么"的错误，不静默改用内置通道（FR-024）。

## 6. 查找

```python
from auto_control_script.matcher.factory import find_by_image, find_by_text

find_by_image(image: Frame, template, threshold: float = 0.95) -> MatchResult
find_by_text(image: Frame, text: str, lang: str = "ch", channel: str = "auto") -> MatchResult
```

未命中返回 `found=False` 且不带坐标（FR-025、FR-026）。

## 7. 脚本与运行

```python
from auto_control_script.script.model import load, save
from auto_control_script.script.runner import Runner

runner = Runner(script, target)
runner.start()          # 开始
runner.pause()          # 在步骤边界暂停
runner.resume()         # 继续
runner.stop(reason)     # 终止并记录原因
runner.step_once()      # 单步执行
runner.retry_step()     # 单步重试
session = runner.session  # RunSession：状态、逐步记录、快照（FR-030、FR-031）
```

同一目标上重复 `start()` 时抛出"该目标已有运行中的会话"错误（边界情况）。

## 8. 稳定性承诺

本契约随 D1「不向后兼容」一次性替换旧接口：旧的窗口/截图/ADB 类与函数不再提供，调用方一律改用上述入口。不提供旧命名别名、兼容层或回退分支（FR-050）。
