# Web API Contract: 统一截图·输入·OCR 自动化平台

**Feature**: `specs/001-auto-control-platform/spec.md` | **Date**: 2026-10-10

Web 层在本机回环地址提供服务（FR-034、假设：单机使用）。接口风格为 REST，运行态使用 SSE 单向推送（D9）。本文件是接口契约，实际路径以服务端自描述文档为准。

## 约定

- 成功返回 `200` 与 JSON；失败返回非 2xx 与 `{"error": {"code": ..., "message": ..., "detail": ...}}`，其中 `message` 为可直接展示给使用者的中文原因（FR-040）。
- 所有坐标与区域与库契约一致：目标客户区逻辑像素（D7）。
- 图像统一以 JPEG 返回，避免 PNG 体积过大拖慢预览。

## 目标

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/targets` | 列出 Windows 窗口与安卓设备，含 `kind/id/name/width/height/available/meta`（FR-035） |
| `GET` | `/api/targets/{id}` | 查询单个目标当前状态与尺寸 |

## 画面预览

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/targets/{id}/frame.jpg` | 返回当前画面 JPEG；支持 `path` 与 `region` 查询参数（FR-036） |
| `GET` | `/api/targets/{id}/frame/meta` | 返回尺寸、实际取图路径、采集时间（FR-049） |

预览为按需拉取，前端定时刷新；不建立长连接（D9）。取图失败时返回明确错误，不返回黑图。

## OCR 与查找

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/ocr` | 入参 `target_id`、`region`、`lang`、`channel`；返回 `items` 与 `channel`、`confidence_available`（FR-023、SC-009） |
| `POST` | `/api/find` | 入参 `target_id`、`by`（`image` / `text`）、模板或文本、`threshold`、`channel`；返回 `MatchResult` |
| `GET` | `/api/ocr/channels` | 返回两类通道的可用状态与缺失的前置条件说明（FR-024、FR-040） |

## 脚本

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/scripts` | 脚本列表（FR-038） |
| `GET` | `/api/scripts/{name}` | 读取脚本 |
| `POST` | `/api/scripts` | 新建 |
| `PUT` | `/api/scripts/{name}` | 保存（FR-037） |
| `DELETE` | `/api/scripts/{name}` | 删除 |
| `POST` | `/api/scripts/import` | 导入文件（FR-029） |
| `GET` | `/api/scripts/{name}/export` | 导出文件（FR-029） |
| `POST` | `/api/scripts/validate` | 校验步骤引用与参数，返回错误清单（FR-040） |

## 运行

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/runs` | 入参 `script`、`target_id`、`from_step`；创建并启动运行（FR-039） |
| `POST` | `/api/runs/{id}/pause` | 在步骤边界暂停（FR-030） |
| `POST` | `/api/runs/{id}/resume` | 继续 |
| `POST` | `/api/runs/{id}/stop` | 终止并记录原因 |
| `POST` | `/api/runs/{id}/step` | 单步执行 |
| `POST` | `/api/runs/{id}/retry-step` | 单步重试（FR-030） |
| `GET` | `/api/runs/{id}` | 运行会话详情与逐步记录（FR-031） |
| `GET` | `/api/runs/{id}/events` | **SSE**：实时推送步骤状态、日志、失败原因（FR-041） |
| `GET` | `/api/runs/{id}/snapshots/{snapshot_id}.jpg` | 步骤画面快照（FR-031、SC-007） |
| `GET` | `/api/runs` | 历史运行列表（支持页面重连后回看） |

SSE 事件类型：`step_started` / `step_finished` / `step_failed` / `session_state` / `log`。断连后可通过 `GET /api/runs/{id}` 补齐状态。

## 错误码

| 码 | 场景 |
|---|---|
| `TARGET_NOT_FOUND` | 目标不存在或已失效（窗口关闭、设备离线） |
| `TARGET_BUSY` | 该目标已有运行中的会话 |
| `CAPTURE_FAILED` | 取图失败或画面无效，附实际取图路径 |
| `CHANNEL_UNAVAILABLE` | 指定的 OCR/取图通道不可用，附缺失前置条件 |
| `ACTION_FAILED` | 动作投递失败，附目标与动作信息 |
| `SCRIPT_INVALID` | 脚本参数非法或步骤引用无效 |
