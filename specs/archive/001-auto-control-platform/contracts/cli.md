# CLI Contract: 统一截图·输入·OCR 自动化平台

**Feature**: `specs/001-auto-control-platform/spec.md` | **Date**: 2026-10-10

命令行通过 `python -m auto_control_script` 进入（FR-042）。所有命令支持 `--json` 输出机器可读结果（FR-043）；不带 `--json` 时输出人类可读文本。错误一律写到 stderr 并以非零退出码结束。

## 全局参数

| 参数 | 说明 |
|---|---|
| `--target <id_or_name>` | 目标标识或名称；省略时由子命令语义决定（如 `targets` 无需目标） |
| `--json` | 结构化输出 |
| `--verbose` | 输出关键决策点日志（取图路径、输入方式、OCR 通道） |

## 子命令

### `targets`

列出可用目标（FR-002、FR-003）。

```text
python -m auto_control_script targets [--kind window|device|all] [--json]
```

输出字段：`kind`、`id`、`name`、`width`、`height`、`available`。

### `capture`

截图并保存为文件（FR-042）。

```text
python -m auto_control_script capture --target <id> --out <path> [--region x1,y1,x2,y2] [--path auto|wgc|printwindow|bitblt|adb]
```

`--json` 时额外输出 `width`、`height`、`captured_at`、`path`（实际使用的取图方式）。

### `ocr`

对当前目标画面或已有图片做 OCR（FR-042）。

```text
python -m auto_control_script ocr [--target <id> | --image <path>] [--region x1,y1,x2,y2] [--lang ch] [--channel auto|builtin|precise] [--json]
```

输出条目：`text`、`box`、`confidence`（不可用时为空）、`order`；`--json` 时附带 `channel`、`confidence_available`。

### `input`

下发单次输入动作（FR-042）。

```text
python -m auto_control_script input --target <id> --action <kind> [--point x,y] [--end-point x,y] [--text <text>] [--mode background|foreground]
```

`<kind>`：`click` / `double_click` / `right_click` / `move` / `drag` / `scroll` / `key` / `hotkey` / `input_text`。
`--mode foreground` 时先输出"将激活目标窗口"的提示（FR-013）。

### `run`

运行脚本文件（FR-042）。

```text
python -m auto_control_script run --script <path> --target <id> [--from-step <n>] [--json]
```

运行过程中逐行输出步骤状态；`--json` 时输出最终的 `RunSession` 摘要（含失败步骤与原因）。

### `script`

脚本管理（FR-029）。

```text
python -m auto_control_script script validate --script <path>    # 校验步骤引用与参数合法性
python -m auto_control_script script info    --script <path>     # 输出步骤概览
```

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 参数或脚本非法（含步骤引用无效、坐标越界、通道不可用等） |
| 3 | 目标不可用（窗口关闭、设备离线） |
| 4 | 执行失败（动作投递失败、画面无效、查找超时并中止） |
| 5 | 依赖的前置条件缺失（高精度通道未安装、adb 不可用）并给出具体说明 |
