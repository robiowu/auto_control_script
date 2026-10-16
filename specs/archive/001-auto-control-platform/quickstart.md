# Quickstart Validation Guide

**Feature**: `specs/001-auto-control-platform/spec.md` | **Date**: 2026-10-10

本文只描述**如何验证能力真的跑通**：前置条件、操作序列与预期结果。实现细节见实现阶段产出的任务与代码，接口细节以 `contracts/` 与 `data-model.md` 为准，本文不重复。

## 0. 前置条件

| 项 | 要求 | 检查方式 |
|---|---|---|
| Python | conda 环境 `python313`（3.13.13） | `conda run -n python313 python -c "import sys;print(sys.version)"` |
| 依赖 | 按新的 `requirements.txt` 安装（当前环境仅有 pillow，必须补装） | `conda run -n python313 pip install -r requirements.txt` |
| 中文输出 | 终端先声明 UTF-8，避免 GBK 编码报错被误判为脚本失败 | `$env:PYTHONIOENCODING='utf-8'` |
| Windows 目标 | 任意一个可打开、标题已知的窗口 | `python -m auto_control_script targets --kind window` |
| 安卓目标（可选） | adb 可用且设备已授权 | `adb devices` 能看到设备；`python -m auto_control_script targets --kind device` |
| 高精度 OCR（可选） | 按项目说明文档启用高精度通道 | `python -m auto_control_script ocr --image <图> --channel precise --json` 返回 `channel: precise` |

安卓设备的验证项在无设备时可跳过，其余全部为必过项。

## 1. 目标枚举（FR-002、FR-003）

```text
python -m auto_control_script targets --json
```

**预期**：列出全部 Windows 窗口，每台已授权安卓设备各一条；每条含 `kind/id/name/width/height/available`。窗口被关闭后再次枚举不再出现。

## 2. 后台截图（FR-006、FR-010）

1. `python -m auto_control_script targets --json` 取一个窗口的 `id`。
2. 用另一个窗口**完全遮挡**该窗口。
3. `python -m auto_control_script capture --target <id> --out frame.jpg --json`

**预期**：保存出该窗口自身内容的图像（不是遮挡它的窗口）；`--json` 输出的 `width/height` 等于窗口客户区尺寸；遮挡窗口的焦点与层级未发生任何变化。手工对比 `--region` 裁剪区域与实际画面位置一致，验证坐标系（D7）。

## 3. OCR 双通道（FR-020、FR-023、SC-009）

1. `python -m auto_control_script ocr --image frame.jpg --json`
2. `python -m auto_control_script ocr --image frame.jpg --channel precise --json`（高精度通道未启用时，预期为退出码 5 且错误信息指出缺少什么）

**预期**：
- 步骤 1 返回按阅读顺序排列的条目，每条含 `text`、`box`、`order`；返回的 `channel` 字段明确是内置还是高精度通道。
- 内置通道结果中 `confidence_available` 为假，置信度字段为空——**不是伪造的数值**（D3）。
- 指定通道与自动选择的结果在 `--json` 中可区分，切换后标识随之改变（SC-009）。
- 用图像上一段已知文字核对：`box` 中心落在该文字所在位置。

## 4. 后台点击（FR-012、SC-002）

1. 打开一个可观察点击结果的窗口（如一个记事本，光标位置可见）。
2. `python -m auto_control_script input --target <id> --action click --point <x>,<y> --mode background`
3. `python -m auto_control_script input --target <id> --action input_text --text "中文abc123" --mode background`

**预期**：目标收到点击与文本，**前台焦点、鼠标位置不变，目标窗口未被置顶**。文本中的中文与数字完整一致（FR-015）。目标被关闭后执行同一命令，预期退出码 3 并给出可读原因（FR-004）。

## 5. 前台点击（FR-013）

`python -m auto_control_script input --target <id> --action click --point <x>,<y> --mode foreground`

**预期**：执行前输出"将激活目标窗口"的提示；执行后目标窗口处于前台且收到点击。

## 6. 查找与定位（FR-025、FR-026）

1. 从步骤 2 的截图中裁一小块作为模板。
2. 用库入口 `find_by_image` / `find_by_text`（见 `contracts/library-api.md`）分别查找存在的与不存在的目标。

**预期**：存在时 `found` 为真且 `point` 落在目标位置；不存在时 `found` 为假、**不带坐标**，且 `detail` 给出原因。

## 7. 网页端到端（FR-034～FR-041、SC-001）

1. `python -m auto_control_script web` 启动，浏览器打开提示的本机地址。
2. 在目标选择器选中一个窗口 → 预览区出现画面。
3. 在预览画面上拖拽框选一个区域 → 区域值填入步骤参数。
4. 依次添加 5 步：等待 → 按字查找 → 点击（引用查找结果）→ 输入文本 → 等待。
5. 保存脚本 → 关闭页面 → 重新打开 → 打开该脚本，步骤与参数完整。
6. 点击运行 → 运行面板逐步显示状态、耗时、画面快照。
7. 运行中点击暂停 → 在步骤边界停下；点击继续 → 从暂停处继续；点击停止 → 立即终止并给出终止原因与所在步骤。
8. 人为把某步坐标改成越界值再运行。

**预期**：全程 15 分钟内完成且无需阅读源码（SC-001）；第 8 步在界面上看到可读的错误提示与出错步骤的画面快照（FR-040、SC-007）。

## 8. 脚本导入导出（FR-029、SC-003）

1. `python -m auto_control_script script validate --script <path>` 应通过。
2. 导出脚本文件，改名后导入，运行。

**预期**：还原后步骤、参数、区域定义完全一致；同一脚本在同一目标连续运行 10 次结果一致、坐标零偏差，无句柄或内存持续增长（SC-003）。

## 9. 高精度通道启用文档（FR-051、SC-008）

按项目说明文档中的高精度 OCR 指引，在一台未启用过的机器上独立完成：安装 → 获取模型 → 启用 → 验证生效 → 遇到模型缺失时按排查步骤恢复。

**预期**：全程无需咨询他人、一次成功；完成后 `ocr --channel precise` 返回 `channel: precise`（SC-008）。

## 10. 清理

- 停止所有运行中的会话，关闭 Web 服务。
- 检查 `%APPDATA%/auto_control_script/runs/` 下的日志与快照是否受保留上限约束（FR-033），超过上限时最旧的被清理。
- 释放所有目标连接与窗口句柄，确认进程退出后无残留。
