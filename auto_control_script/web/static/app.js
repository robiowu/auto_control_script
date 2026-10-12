/*
 * app.js - 网页界面交互逻辑
 *
 * 职责:
 * - 目标选择、画面预览、拖拽框选取点
 * - 步骤编排与脚本保存/打开/删除/导出
 * - 运行控制与 SSE 运行日志订阅
 *
 * 调用链:
 * - 浏览器 -> app.js -> /api/* -> web/app.py
 */

"use strict";

const state = {
  targetId: "",
  steps: [],
  scriptName: "",
  runId: "",
  eventSource: null,
  imageScale: 1,
};

const el = (id) => document.getElementById(id);

function toast(message, isError) {
  const item = document.createElement("div");
  item.className = "item" + (isError ? " error" : "");
  item.textContent = message;
  el("toast").appendChild(item);
  setTimeout(() => item.remove(), isError ? 8000 : 3000);
}

async function api(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch (error) {
    data = text;
  }
  if (!response.ok) {
    const detail = data && data.error ? data.error.message : (data && data.detail ? data.detail : text);
    throw new Error(detail || `请求失败：${response.status}`);
  }
  return data;
}

function postJson(url, body) {
  return api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function parseList(text) {
  if (!text) {
    return null;
  }
  return text.split(",").map((item) => Number(item.trim())).filter((item) => !Number.isNaN(item));
}

// ------------------------------------------------------------------ 目标

async function refreshTargets() {
  const targets = await api("/api/targets");
  const select = el("target-select");
  select.innerHTML = "";
  targets.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `[${item.kind}] ${item.name} (${item.width}x${item.height})`;
    select.appendChild(option);
  });
  if (targets.length > 0) {
    if (!state.targetId || !targets.some((item) => item.id === state.targetId)) {
      state.targetId = targets[0].id;
    }
    select.value = state.targetId;
    updateTargetInfo();
  }
}

function updateTargetInfo() {
  const option = el("target-select").selectedOptions[0];
  el("target-info").textContent = option ? option.textContent : "";
}

// ------------------------------------------------------------------ 预览与取点

function previewUrl() {
  const params = new URLSearchParams({ t: String(Date.now()) });
  const path = el("capture-path").value;
  if (path) {
    params.set("path", path);
  }
  return `/api/targets/${encodeURIComponent(state.targetId)}/frame.jpg?${params.toString()}`;
}

async function refreshPreview() {
  if (!state.targetId) {
    return;
  }
  const image = el("preview-image");
  image.src = previewUrl();
  await new Promise((resolve) => {
    image.onload = resolve;
    image.onerror = resolve;
  });
  const rect = image.getBoundingClientRect();
  state.imageScale = image.naturalWidth ? image.naturalWidth / rect.width : 1;
  el("preview-overlay").innerHTML = "";
}

function setupSelection() {
  const overlay = el("preview-overlay");
  let startPoint = null;
  let box = null;

  overlay.addEventListener("mousedown", (event) => {
    const rect = overlay.getBoundingClientRect();
    startPoint = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    box = document.createElement("div");
    box.className = "selection";
    overlay.appendChild(box);
  });

  overlay.addEventListener("mousemove", (event) => {
    if (!box) {
      return;
    }
    const rect = overlay.getBoundingClientRect();
    const current = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    box.style.left = `${Math.min(startPoint.x, current.x)}px`;
    box.style.top = `${Math.min(startPoint.y, current.y)}px`;
    box.style.width = `${Math.abs(current.x - startPoint.x)}px`;
    box.style.height = `${Math.abs(current.y - startPoint.y)}px`;
  });

  overlay.addEventListener("mouseup", (event) => {
    if (!box) {
      return;
    }
    const rect = overlay.getBoundingClientRect();
    const end = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    const scale = state.imageScale;
    const x1 = Math.round(Math.min(startPoint.x, end.x) * scale);
    const y1 = Math.round(Math.min(startPoint.y, end.y) * scale);
    const x2 = Math.round(Math.max(startPoint.x, end.x) * scale);
    const y2 = Math.round(Math.max(startPoint.y, end.y) * scale);
    box.remove();
    box = null;
    startPoint = null;
    if (x2 - x1 < 3 || y2 - y1 < 3) {
      el("coord-point").value = `${x1},${y1}`;
      toast(`已取点：${x1},${y1}`);
      return;
    }
    el("coord-region").value = `${x1},${y1},${x2},${y2}`;
    toast(`已框选区域：${x1},${y1},${x2},${y2}`);
  });
}

async function recognizePreview() {
  if (!state.targetId) {
    return;
  }
  const channel = el("ocr-channel").value || null;
  const result = await postJson("/api/ocr", {
    target_id: state.targetId,
    channel: channel,
    path: el("capture-path").value || null,
  });
  toast(
    `通道=${result.channel}（${result.channel_reason}），置信度可用=${result.confidence_available}，共 ${result.items.length} 条\n` +
      result.items.slice(0, 8).map((item) => `[${item.order}] ${item.text}`).join("\n")
  );
}

// ------------------------------------------------------------------ 步骤编排

function renderSteps(currentIndex) {
  const list = el("step-list");
  list.innerHTML = "";
  state.steps.forEach((step, index) => {
    const item = document.createElement("li");
    if (index === currentIndex) {
      item.className = "current";
    }
    const summary = document.createElement("span");
    summary.className = "grow";
    summary.textContent =
      `${index + 1}. ${step.id} ${step.type}` +
      (step.params && step.params.text ? ` 文本=${step.params.text}` : "") +
      (step.params && step.params.point ? ` 坐标=${step.params.point}` : "") +
      (step.ref ? ` 引用=${step.ref}` : "");
    item.appendChild(summary);
    ["↑", "↓", "删"].forEach((label, buttonIndex) => {
      const button = document.createElement("button");
      button.textContent = label;
      button.onclick = () => {
        if (buttonIndex === 0 && index > 0) {
          [state.steps[index - 1], state.steps[index]] = [state.steps[index], state.steps[index - 1]];
        } else if (buttonIndex === 1 && index < state.steps.length - 1) {
          [state.steps[index + 1], state.steps[index]] = [state.steps[index], state.steps[index + 1]];
        } else if (buttonIndex === 2) {
          state.steps.splice(index, 1);
        }
        renderSteps(currentIndex);
      };
      item.appendChild(button);
    });
    list.appendChild(item);
  });
}

function buildStepFromForm() {
  const type = el("step-type").value;
  const id = el("step-id").value.trim() || `s${state.steps.length + 1}`;
  const params = {};
  const text = el("step-text").value.trim();
  const point = parseList(el("step-point").value);
  const endPoint = parseList(el("step-end").value);
  const region = parseList(el("step-region").value);
  const extra = el("step-extra").value.trim();

  if (text) {
    params.text = text;
  }
  if (point) {
    params.point = point;
  }
  if (endPoint) {
    params.end_point = endPoint;
  }
  if (region) {
    params.region = region;
  }
  if (type === "find_image" && !params.template) {
    params.template = text;
  }
  if (type === "key" && text) {
    params.key = text;
  }
  if (type === "scroll" && text) {
    params.amount = Number(text);
  }
  if (extra) {
    extra.split(";").forEach((pair) => {
      const [key, value] = pair.split("=");
      if (key && value !== undefined) {
        params[key.trim()] = isNaN(Number(value)) ? value.trim() : Number(value);
      }
    });
  }
  return {
    id: id,
    type: type,
    enabled: true,
    params: params,
    ref: el("step-ref").value.trim() || null,
    on_fail: el("step-onfail").value,
    timeout: Number(el("step-timeout").value) || 0,
    note: "",
  };
}

function buildScriptPayload() {
  const target = el("target-select").selectedOptions[0];
  return {
    script: {
      name: el("script-name").value.trim() || "未命名脚本",
      version: 1,
      base_width: 0,
      base_height: 0,
      target_kind: target && target.textContent.includes("[window]") ? "window" : "device",
      steps: state.steps,
      options: {},
    },
  };
}

async function refreshScriptList() {
  const names = await api("/api/scripts");
  const select = el("script-select");
  select.innerHTML = "";
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
}

function applyScript(data) {
  state.scriptName = data.name || "";
  el("script-name").value = state.scriptName;
  state.steps = (data.steps || []).map((step) => ({
    id: step.id,
    type: step.type,
    enabled: step.enabled !== false,
    params: step.params || {},
    ref: step.ref || null,
    on_fail: step.on_fail || "abort",
    timeout: step.timeout || 0,
    note: step.note || "",
  }));
  renderSteps(-1);
}

// ------------------------------------------------------------------ 运行

function logLine(text, className) {
  const line = document.createElement("div");
  line.className = "line " + (className || "");
  line.textContent = text;
  const box = el("run-log");
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function subscribeEvents(runId) {
  if (state.eventSource) {
    state.eventSource.close();
  }
  const source = new EventSource(`/api/runs/${runId}/events`);
  state.eventSource = source;
  ["step_success", "step_failed", "step_skipped"].forEach((name) => {
    source.addEventListener(name, (event) => {
      const record = JSON.parse(event.data);
      const detail = record.detail ? JSON.stringify(record.detail) : "";
      logLine(
        `[${record.index + 1}] ${record.step_id} -> ${record.status} (${record.duration}s) ${detail}`,
        record.status
      );
      if (record.error) {
        logLine(`    原因：${record.error}`, "failed");
      }
      renderSteps(record.index);
    });
  });
  source.addEventListener("session_state", (event) => {
    const data = JSON.parse(event.data);
    el("run-state").textContent = `状态=${data.state} 当前步骤=${data.current_step_index + 1}`;
    if (data.state === "succeeded" || data.state === "failed" || data.state === "stopped") {
      logLine(`运行结束，状态=${data.state}`);
      source.close();
    }
  });
}

async function startRun() {
  if (!state.targetId || state.steps.length === 0) {
    toast("请先选择目标并添加至少一个步骤", true);
    return;
  }
  el("run-log").innerHTML = "";
  const response = await postJson("/api/runs", {
    script: el("script-name").value.trim() || "未命名脚本",
    target_id: state.targetId,
  });
  state.runId = response.id;
  logLine(`开始运行，会话 ${response.id}`);
  subscribeEvents(response.id);
}

function runAction(name) {
  if (!state.runId) {
    toast("尚未开始运行", true);
    return;
  }
  postJson(`/api/runs/${state.runId}/${name}`, {})
    .then((data) => {
      if (data && data.state) {
        el("run-state").textContent = `状态=${data.state}`;
      }
      if (data && data.status) {
        logLine(`单步结果：步骤 ${data.index + 1} -> ${data.status}`);
      }
    })
    .catch((error) => toast(error.message, true));
}

// ------------------------------------------------------------------ 初始化

function bindEvents() {
  el("btn-refresh-targets").onclick = () => refreshTargets().catch((error) => toast(error.message, true));
  el("target-select").onchange = () => {
    state.targetId = el("target-select").value;
    updateTargetInfo();
    refreshPreview();
  };
  el("btn-preview").onclick = () => refreshPreview().catch((error) => toast(error.message, true));
  el("btn-ocr").onclick = () => recognizePreview().catch((error) => toast(error.message, true));

  el("btn-add-step").onclick = () => {
    state.steps.push(buildStepFromForm());
    renderSteps(-1);
  };
  el("btn-save-script").onclick = () => {
    const name = el("script-name").value.trim();
    if (!name) {
      toast("请先填写脚本名", true);
      return;
    }
    postJson(`/api/scripts/${encodeURIComponent(name)}`, buildScriptPayload())
      .then(() => {
        toast(`脚本 ${name} 已保存`);
        refreshScriptList();
      })
      .catch((error) => toast(error.message, true));
  };
  el("btn-load-script").onclick = () => {
    const name = el("script-select").value;
    if (!name) {
      toast("请先选择脚本", true);
      return;
    }
    api(`/api/scripts/${encodeURIComponent(name)}`)
      .then((data) => {
        applyScript(data);
        toast(`已打开脚本 ${name}`);
      })
      .catch((error) => toast(error.message, true));
  };
  el("btn-new-script").onclick = () => {
    state.steps = [];
    state.scriptName = "";
    el("script-name").value = "";
    renderSteps(-1);
  };
  el("btn-delete-script").onclick = () => {
    const name = el("script-select").value;
    if (!name) {
      return;
    }
    api(`/api/scripts/${encodeURIComponent(name)}`, { method: "DELETE" })
      .then(() => {
        toast(`已删除脚本 ${name}`);
        refreshScriptList();
      })
      .catch((error) => toast(error.message, true));
  };
  el("btn-export-script").onclick = () => {
    const name = el("script-select").value || el("script-name").value.trim();
    if (!name) {
      return;
    }
    api(`/api/scripts/${encodeURIComponent(name)}`).then((data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${name}.json`;
      link.click();
    }).catch((error) => toast(error.message, true));
  };

  el("btn-run").onclick = () => startRun().catch((error) => toast(error.message, true));
  el("btn-pause").onclick = () => runAction("pause");
  el("btn-resume").onclick = () => runAction("resume");
  el("btn-stop").onclick = () => runAction("stop");
  el("btn-step").onclick = () => runAction("step");
  el("btn-retry").onclick = () => runAction("retry-step");
}

window.addEventListener("load", () => {
  bindEvents();
  setupSelection();
  refreshTargets()
    .then(() => refreshPreview())
    .then(() => refreshScriptList())
    .catch((error) => toast(error.message, true));
});
