(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { me: null, runs: [], selected: null, timer: null, locale: "en" };
  const messages = {
    en: {
      "eyebrow.operations": "OPERATIONS", "eyebrow.pipeline": "PIPELINE", "app.title": "Rockbase Console",
      "language.label": "Language", "auth.username": "Username", "auth.password": "Password", "auth.signIn": "Sign in", "auth.signOut": "Sign out",
      "runs.title": "Runs", "runs.new": "New", "runs.noneSelected": "No run selected", "runs.controls": "Run controls",
      "stage.current": "Current stage", "stage.selectPrompt": "Select a run to inspect stage details.", "stage.noStages": "No stages recorded",
      "actions.pause": "Pause", "actions.resume": "Resume", "actions.approve": "Approve gate", "actions.terminate": "Terminate", "actions.cancel": "Cancel",
      "audit.title": "Audit stream", "dialogs.terminateTitle": "Terminate run?", "dialogs.approveTitle": "Approve write gate",
      "dialogs.gate": "Gate", "dialogs.batchLabel": "Type batch label to confirm", "gates.send": "Send", "gates.sync": "Sync",
      "messages.actionAccepted": "Action accepted", "messages.terminateConfirm": "Terminate {run}? This cannot be undone.",
      "status.unknown": "unknown", "status.pending": "pending", "status.completed": "completed", "status.running": "running",
      "status.retrying": "retrying", "status.paused": "paused", "status.failed": "failed", "status.interrupted": "interrupted",
      "errors.requestFailed": "Request failed ({status})"
    },
    "zh-CN": {
      "eyebrow.operations": "运行运维", "eyebrow.pipeline": "流水线", "app.title": "Rockbase 控制台",
      "language.label": "语言", "auth.username": "用户名", "auth.password": "密码", "auth.signIn": "登录", "auth.signOut": "退出登录",
      "runs.title": "运行任务", "runs.new": "新建", "runs.noneSelected": "未选择运行任务", "runs.controls": "运行控制",
      "stage.current": "当前阶段", "stage.selectPrompt": "请选择运行任务以查看阶段详情。", "stage.noStages": "暂无阶段记录",
      "actions.pause": "暂停", "actions.resume": "恢复", "actions.approve": "批准写入闸门", "actions.terminate": "终止", "actions.cancel": "取消",
      "audit.title": "审计流", "dialogs.terminateTitle": "终止运行任务？", "dialogs.approveTitle": "批准写入闸门",
      "dialogs.gate": "闸门", "dialogs.batchLabel": "输入批次标签以确认", "gates.send": "发送", "gates.sync": "同步",
      "messages.actionAccepted": "操作已受理", "messages.terminateConfirm": "确定终止 {run}？此操作无法撤销。",
      "status.unknown": "未知", "status.pending": "等待中", "status.completed": "已完成", "status.running": "运行中",
      "status.retrying": "重试中", "status.paused": "已暂停", "status.failed": "失败", "status.interrupted": "已中断",
      "errors.requestFailed": "请求失败（{status}）"
    }
  };
  const translate = (key, vars = {}) => {
    let text = messages[state.locale][key] || messages.en[key] || key;
    Object.entries(vars).forEach(([name, value]) => { text = text.replace(`{${name}}`, value); });
    return text;
  };
  const statusLabel = (status) => translate(`status.${status || "unknown"}`);
  const api = async (path, options = {}) => {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || translate("errors.requestFailed", { status: response.status }));
    return payload;
  };
  const show = (id, visible) => { $(id).hidden = !visible; };
  const message = (text, error = false) => { $("action-message").textContent = text; $("action-message").className = error ? "action-message error" : "action-message"; };

  function applyLocale(locale) {
    state.locale = messages[locale] ? locale : "en";
    localStorage.setItem("rockbase-console-locale", state.locale);
    document.documentElement.lang = state.locale === "zh-CN" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = translate(node.dataset.i18n); });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => { node.setAttribute("aria-label", translate(node.dataset.i18nAriaLabel)); });
    document.querySelectorAll(".language-button").forEach((button) => {
      const selected = button.dataset.locale === state.locale;
      button.setAttribute("aria-pressed", String(selected));
    });
    renderRuns();
    if (state.selected) renderRun(state.runs.find((run) => run.run_id === state.selected) || null);
  }
  function renderRuns() {
    const list = $("run-list"); list.textContent = "";
    state.runs.forEach((run) => {
      const item = document.createElement("li"); const button = document.createElement("button");
      button.className = `run-item${run.run_id === state.selected ? " selected" : ""}`;
      button.type = "button"; button.dataset.runId = run.run_id;
      const id = document.createElement("strong"); id.textContent = run.run_id;
      const status = document.createElement("small"); status.textContent = statusLabel(run.status);
      button.append(id, status); item.append(button); list.append(item);
    });
  }
  function renderStages(run) {
    const timeline = $("stage-timeline"); timeline.textContent = "";
    const stages = run ? run.stages : state.stages;
    const entries = Object.entries(stages || {});
    entries.forEach(([name, record]) => {
      const item = document.createElement("li"); item.className = "stage"; item.dataset.status = record.status || "pending";
      const stageName = document.createElement("span"); stageName.className = "stage-name"; stageName.textContent = name;
      const stageStatus = document.createElement("span"); stageStatus.className = "stage-status"; stageStatus.textContent = statusLabel(record.status);
      item.append(stageName, stageStatus); timeline.append(item);
    });
    const current = entries.find(([, record]) => ["running", "retrying", "paused"].includes(record.status)) || entries[entries.length - 1];
    $("current-stage").textContent = current ? `${current[0]} · ${statusLabel(current[1].status)}` : translate("stage.noStages");
    $("stage-output").textContent = current ? [current[1].stdout, current[1].stderr].filter(Boolean).join("\n") : "";
  }
  function renderRun(run) {
    $("selected-run-title").textContent = run ? run.run_id : translate("runs.noneSelected");
    $("run-status").textContent = run ? statusLabel(run.status) : ""; renderStages(run);
    const operator = state.me?.role === "operator"; const active = ["running", "retrying"].includes(run?.status);
    $("pause-button").hidden = !(operator && active); $("resume-button").hidden = !(operator && run?.status === "paused");
    $("approve-button").hidden = !operator; $("kill-button").hidden = !(operator && active);
  }
  async function refresh() {
    try {
      const runs = await api("/api/runs"); state.runs = runs.runs || [];
      if (!state.selected && state.runs[0]) state.selected = state.runs[0].run_id;
      renderRuns();
      if (state.selected) renderRun(await api(`/api/runs/${encodeURIComponent(state.selected)}`));
      const audit = await api("/api/audit"); const list = $("audit-list"); list.textContent = "";
      (audit.events || []).forEach((event) => { const item = document.createElement("li"); item.textContent = `${event.timestamp || ""} ${event.actor || ""} ${event.event || ""}`; list.append(item); });
    } catch (error) { message(error.message, true); }
  }
  function csrfHeaders() { return state.me?.csrf_token ? { "X-CSRF-Token": state.me.csrf_token } : {}; }
  async function mutate(path, body = {}) { const result = await api(path, { method: "POST", headers: csrfHeaders(), body: JSON.stringify(body) }); message(translate("messages.actionAccepted")); await refresh(); return result; }
  async function login(event) { event.preventDefault(); $("login-error").textContent = ""; try { await api("/api/login", { method: "POST", body: JSON.stringify({ username: $("username").value, password: $("password").value }) }); state.me = await api("/api/me"); $("identity-label").textContent = `${state.me.username} · ${state.me.role}`; show("login-view", false); show("console-view", true); await refresh(); startPolling(); } catch (error) { $("login-error").textContent = error.message; } }
  function startPolling() { if (!state.timer) state.timer = setInterval(() => { if (!document.hidden) refresh(); }, 2000); }
  function stopPolling() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }
  $("login-form").addEventListener("submit", login);
  document.querySelectorAll(".language-button").forEach((button) => button.addEventListener("click", () => applyLocale(button.dataset.locale)));
  $("run-list").addEventListener("click", (event) => { const button = event.target.closest("button[data-run-id]"); if (button) { state.selected = button.dataset.runId; refresh(); } });
  $("pause-button").addEventListener("click", () => mutate(`/api/runs/${state.selected}/pause`));
  $("resume-button").addEventListener("click", () => mutate(`/api/runs/${state.selected}/resume`));
  $("approve-button").addEventListener("click", () => $("approval-dialog").showModal());
  $("approval-cancel").addEventListener("click", () => $("approval-dialog").close());
  $("approval-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await mutate(`/api/runs/${state.selected}/approve`, { gate: $("approval-gate").value, batch_label: $("batch-label").value }); $("approval-dialog").close(); } catch (error) { message(error.message, true); } });
  $("kill-button").addEventListener("click", () => { $("kill-confirmation").textContent = translate("messages.terminateConfirm", { run: state.selected }); $("kill-dialog").showModal(); });
  $("kill-confirm").addEventListener("click", async (event) => { event.preventDefault(); try { await mutate(`/api/runs/${state.selected}/kill`); $("kill-dialog").close(); } catch (error) { message(error.message, true); } });
  $("logout-button").addEventListener("click", async () => { try { await mutate("/api/logout"); } finally { stopPolling(); state.me = null; show("console-view", false); show("login-view", true); } });
  $("new-run-button").addEventListener("click", () => message(state.locale === "zh-CN" ? "请使用 API 启动表单定义批次。" : "Use the API start form to define a batch."));
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopPolling(); else if (state.me) { refresh(); startPolling(); } });
  applyLocale(localStorage.getItem("rockbase-console-locale") || "en");
  api("/api/me").then((me) => { state.me = me; $("identity-label").textContent = `${me.username} · ${me.role}`; show("login-view", false); show("console-view", true); refresh(); startPolling(); }).catch(() => show("login-view", true));
})();
