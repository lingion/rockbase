(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { me: null, runs: [], selected: null, timer: null, locale: "en", busy: false, artifacts: [], artifactBusy: false, feedbackTarget: null };
  const messages = {
    en: {
      "eyebrow.operations": "Operations console", "eyebrow.pipeline": "Pipeline", "app.title": "Rockbase",
      "auth.intro": "Observe runs, approve writes, and keep the pipeline moving.", "auth.localOnly": "Local operator access · activity is recorded in the audit stream.",
      "language.label": "Language", "auth.username": "Username", "auth.password": "Password", "auth.signIn": "Sign in", "auth.signOut": "Sign out",
      "connection.live": "Loopback live", "runs.title": "Runs", "runs.new": "New run", "runs.search": "Search runs", "runs.empty": "No runs match this search.", "runs.noneSelected": "No run selected",
      "summary.started": "Started", "summary.stages": "Stages", "summary.updated": "Last update", "stage.title": "Stage pulse", "stage.subtitle": "The current run, from intake to sync.", "stage.currentLabel": "Current stage", "stage.current": "Select a run to inspect stage details.", "stage.noStages": "No stages recorded", "stage.progress": "{done} of {total} complete",
      "actions.pause": "Pause", "actions.resume": "Resume", "actions.approve": "Approve gate", "actions.terminate": "Terminate", "actions.cancel": "Cancel",
      "audit.kicker": "Trace", "audit.title": "Audit stream", "audit.subtitle": "Recent operator activity", "audit.empty": "No operator activity yet.",
      "dialogs.terminateTitle": "Terminate run?", "dialogs.approveTitle": "Approve write gate", "dialogs.approveCopy": "This approval authorizes one controlled write path for the selected run.", "dialogs.gate": "Gate", "dialogs.batchLabel": "Type batch label to confirm", "gates.send": "Send", "gates.sync": "Sync",
      "messages.actionAccepted": "Action accepted", "messages.working": "Working…", "messages.terminateConfirm": "Terminate {run}? This cannot be undone.", "messages.newRun": "Use the API start form to define a batch.",
      "artifacts.title": "Stage approval", "artifacts.subtitle": "Each card is read-only until you decide.", "artifacts.empty": "No pending decisions.", "artifacts.reject": "Reject", "artifacts.rejectWithFeedback": "Reject with feedback", "artifacts.stageLabel": "Stage", "artifacts.versionLabel": "Version", "artifacts.validationOk": "Validation passed", "artifacts.validationFailed": "Validation failed: {errors}", "artifacts.confidence": "Confidence {value}", "artifacts.evidence": "Evidence", "artifacts.pending": "Pending decision", "artifacts.decided": "Decision recorded", "artifacts.stale": "Decision outdated — refresh and try again.", "artifacts.feedbackCopy": "Rejecting artifact {artifact} for stage {stage}. Operators reading the regenerated envelope will see this feedback.",
      "status.unknown": "unknown", "status.pending": "pending", "status.completed": "completed", "status.running": "running", "status.retrying": "retrying", "status.paused": "paused", "status.failed": "failed", "status.interrupted": "interrupted",
      "errors.requestFailed": "Request failed ({status})"
    },
    "zh-CN": {
      "eyebrow.operations": "运行控制台", "eyebrow.pipeline": "流水线", "app.title": "Rockbase",
      "auth.intro": "观察运行、批准写入，让流水线持续前进。", "auth.localOnly": "本地操作员访问 · 所有活动都会记录在审计流中。",
      "language.label": "语言", "auth.username": "用户名", "auth.password": "密码", "auth.signIn": "登录", "auth.signOut": "退出登录",
      "connection.live": "本地连接正常", "runs.title": "运行任务", "runs.new": "新建运行", "runs.search": "搜索运行任务", "runs.empty": "没有匹配的运行任务。", "runs.noneSelected": "未选择运行任务",
      "summary.started": "开始时间", "summary.stages": "阶段数", "summary.updated": "最近更新", "stage.title": "阶段脉冲", "stage.subtitle": "从接收数据到同步的当前运行。", "stage.currentLabel": "当前阶段", "stage.current": "请选择运行任务以查看阶段详情。", "stage.noStages": "暂无阶段记录", "stage.progress": "已完成 {done} / {total}",
      "actions.pause": "暂停", "actions.resume": "恢复", "actions.approve": "批准闸门", "actions.terminate": "终止", "actions.cancel": "取消",
      "audit.kicker": "追踪", "audit.title": "审计流", "audit.subtitle": "最近的操作员活动", "audit.empty": "暂无操作员活动。",
      "dialogs.terminateTitle": "终止运行任务？", "dialogs.approveTitle": "批准写入闸门", "dialogs.approveCopy": "此批准将授权所选运行任务的一条受控写入路径。", "dialogs.gate": "闸门", "dialogs.batchLabel": "输入批次标签以确认", "gates.send": "发送", "gates.sync": "同步",
      "messages.actionAccepted": "操作已受理", "messages.working": "处理中…", "messages.terminateConfirm": "确定终止 {run}？此操作无法撤销。", "messages.newRun": "请使用 API 启动表单定义批次。",
      "artifacts.title": "阶段审批", "artifacts.subtitle": "每张卡片在您做出决定前均为只读。", "artifacts.empty": "暂无待审批事项。", "artifacts.reject": "驳回", "artifacts.rejectWithFeedback": "附意见驳回", "artifacts.stageLabel": "阶段", "artifacts.versionLabel": "版本", "artifacts.validationOk": "校验通过", "artifacts.validationFailed": "校验失败：{errors}", "artifacts.confidence": "置信度 {value}", "artifacts.evidence": "依据", "artifacts.pending": "待决定", "artifacts.decided": "已记录决定", "artifacts.stale": "决定已过期——请刷新后重试。", "artifacts.feedbackCopy": "将为阶段 {stage} 驳回产物 {artifact}。重新生成的结果将带上此反馈。",
      "status.unknown": "未知", "status.pending": "等待中", "status.completed": "已完成", "status.running": "运行中", "status.retrying": "重试中", "status.paused": "已暂停", "status.failed": "失败", "status.interrupted": "已中断",
      "errors.requestFailed": "请求失败（{status}）"
    }
  };

  const translate = (key, vars = {}) => {
    let text = messages[state.locale][key] || messages.en[key] || key;
    Object.entries(vars).forEach(([name, value]) => { text = text.replace(`{${name}}`, value); });
    return text;
  };
  const statusLabel = (status) => translate(`status.${status || "unknown"}`);
  const formatTime = (value) => {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? String(value) : new Intl.DateTimeFormat(state.locale, { dateStyle: "short", timeStyle: "short" }).format(date);
  };
  const show = (id, visible) => { $(id).hidden = !visible; };
  const message = (text, error = false) => { $("action-message").textContent = text; $("action-message").className = error ? "action-message error" : "action-message"; };
  const setBusy = (busy) => { state.busy = busy; document.querySelectorAll(".action-button").forEach((button) => { button.disabled = busy; }); };

  const api = async (path, options = {}) => {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || translate("errors.requestFailed", { status: response.status }));
    return payload;
  };

  function applyLocale(locale) {
    state.locale = messages[locale] ? locale : "en";
    localStorage.setItem("rockbase-console-locale", state.locale);
    document.documentElement.lang = state.locale === "zh-CN" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = translate(node.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => { node.placeholder = translate(node.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => { node.setAttribute("aria-label", translate(node.dataset.i18nAriaLabel)); });
    document.querySelectorAll(".language-button").forEach((button) => { button.setAttribute("aria-pressed", String(button.dataset.locale === state.locale)); });
    renderRuns();
    if (state.selected) renderRun(state.runs.find((run) => run.run_id === state.selected) || null);
  }

  function visibleRuns() {
    const query = $("run-search")?.value.trim().toLowerCase() || "";
    return state.runs.filter((run) => !query || String(run.run_id).toLowerCase().includes(query) || String(run.status || "").toLowerCase().includes(query));
  }

  function markerClass(status) { return `status-marker status-marker-${status || "unknown"}`; }

  function renderRuns() {
    const list = $("run-list"); list.textContent = "";
    const runs = visibleRuns();
    $("run-count").textContent = String(state.runs.length);
    show("run-empty", runs.length === 0);
    runs.forEach((run) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.className = `run-item${run.run_id === state.selected ? " selected" : ""}`;
      button.type = "button"; button.dataset.runId = run.run_id; button.setAttribute("aria-current", run.run_id === state.selected ? "true" : "false");
      const id = document.createElement("strong"); id.textContent = run.run_id;
      const meta = document.createElement("span"); meta.className = "run-meta";
      const marker = document.createElement("span"); marker.className = markerClass(run.status); marker.setAttribute("aria-hidden", "true");
      const status = document.createElement("span"); status.textContent = statusLabel(run.status);
      meta.append(marker, status); button.append(id, meta); item.append(button); list.append(item);
    });
  }

  function renderStages(run) {
    const timeline = $("stage-timeline"); timeline.textContent = "";
    const entries = Object.entries(run?.stages || {});
    const done = entries.filter(([, record]) => record.status === "completed").length;
    $("stage-progress").textContent = entries.length ? translate("stage.progress", { done, total: entries.length }) : "";
    entries.forEach(([name, record]) => {
      const item = document.createElement("li"); item.className = "stage"; item.dataset.status = record.status || "pending";
      const stageName = document.createElement("span"); stageName.className = "stage-name"; stageName.textContent = name;
      const stageStatus = document.createElement("span"); stageStatus.className = "stage-status"; stageStatus.textContent = statusLabel(record.status);
      item.append(stageName, stageStatus); timeline.append(item);
    });
    const current = entries.find(([, record]) => ["running", "retrying", "paused"].includes(record.status)) || entries.find(([, record]) => record.status === "failed") || entries[entries.length - 1];
    $("current-stage-title").textContent = current ? current[0] : translate("stage.current");
    $("stage-status-chip").textContent = current ? statusLabel(current[1].status) : "";
    $("stage-status-chip").dataset.status = current?.[1]?.status || "";
    $("stage-output").textContent = current ? [current[1].stdout, current[1].stderr, current[1].error].filter(Boolean).join("\n") : "";
  }

  function renderRun(run) {
    $("selected-run-title").textContent = run ? run.run_id : translate("runs.noneSelected");
    $("run-status").textContent = run ? statusLabel(run.status) : "";
    $("run-status").dataset.status = run?.status || "";
    $("run-started").textContent = formatTime(run?.started_at || run?.created_at);
    $("run-updated").textContent = formatTime(run?.updated_at || run?.finished_at);
    $("run-stage-count").textContent = run?.stages ? String(Object.keys(run.stages).length) : "—";
    renderStages(run);
    const operator = state.me?.role === "operator"; const active = ["running", "retrying"].includes(run?.status);
    $("pause-button").hidden = !(operator && active); $("resume-button").hidden = !(operator && run?.status === "paused");
    $("approve-button").hidden = !operator; $("kill-button").hidden = !(operator && active);
  }

  async function refresh() {
    try {
      const runs = await api("/api/runs"); state.runs = runs.runs || [];
      if (state.selected && !state.runs.some((run) => run.run_id === state.selected)) state.selected = null;
      if (!state.selected && state.runs[0]) state.selected = state.runs[0].run_id;
      renderRuns();
      renderRun(state.selected ? await api(`/api/runs/${encodeURIComponent(state.selected)}`) : null);
      if (state.selected) await refreshArtifacts(state.selected);
      const audit = await api("/api/audit"); const list = $("audit-list"); list.textContent = "";
      show("audit-empty", !(audit.events || []).length);
      (audit.events || []).forEach((event) => { const item = document.createElement("li"); item.textContent = `${formatTime(event.timestamp)}  ${event.actor || ""}  ${event.event || ""}`; list.append(item); });
    } catch (error) { message(error.message, true); }
  }

  function csrfHeaders() { return state.me?.csrf_token ? { "X-CSRF-Token": state.me.csrf_token } : {}; }
  async function mutate(path, body = {}) { setBusy(true); message(translate("messages.working")); try { const result = await api(path, { method: "POST", headers: csrfHeaders(), body: JSON.stringify(body) }); message(translate("messages.actionAccepted")); await refresh(); return result; } catch (error) { message(error.message, true); throw error; } finally { setBusy(false); } }

  async function refreshArtifacts(runId) {
    if (!runId) { renderArtifacts([]); return; }
    try {
      const payload = await api(`/api/runs/${encodeURIComponent(runId)}/artifacts`);
      renderArtifacts(payload.artifacts || []);
    } catch (error) {
      renderArtifacts([]);
      message(error.message, true);
    }
  }

  function decisionStatus(stageRecord) {
    if (!stageRecord) return "pending";
    if (stageRecord.status === "awaiting_approval") return "pending";
    if (stageRecord.status === "completed" && stageRecord.decision_status === "approved") return "approved";
    return "pending";
  }

  function renderArtifacts(items) {
    state.artifacts = items;
    const list = $("artifact-list"); list.textContent = "";
    const isOperator = state.me?.role === "operator";
    const empty = items.length === 0;
    show("artifact-empty", empty);
    show("artifact-panel", !empty || isOperator);
    show("artifact-busy-label", state.artifactBusy);
    $("artifact-busy-label").textContent = state.artifactBusy ? translate("messages.working") : "";
    items.forEach((artifact) => {
      const card = document.createElement("li");
      card.className = "artifact-card";
      card.dataset.artifactId = artifact.artifact_id;
      card.dataset.version = String(artifact.version);
      const status = artifact.decision_status || "awaiting_approval";
      card.dataset.decisionStatus = status;

      const heading = document.createElement("div"); heading.className = "artifact-heading";
      const stage = document.createElement("span"); stage.className = "artifact-stage"; stage.textContent = `${translate("artifacts.stageLabel")}: ${artifact.stage_id}`;
      const version = document.createElement("span"); version.className = "artifact-version"; version.textContent = `${translate("artifacts.versionLabel")}: v${artifact.version}`;
      const statusBadge = document.createElement("span"); statusBadge.className = "artifact-decision-status";
      statusBadge.textContent = status === "approved" ? translate("artifacts.decided") : translate("artifacts.pending");
      heading.append(stage, version, statusBadge);

      const validation = document.createElement("p"); validation.className = "artifact-validation";
      const errors = (artifact.validation?.errors || []);
      validation.textContent = errors.length === 0
        ? translate("artifacts.validationOk")
        : translate("artifacts.validationFailed", { errors: errors.join("; ") });
      if (errors.length > 0) card.dataset.validationState = "failed";

      const summary = document.createElement("pre"); summary.className = "artifact-summary"; summary.textContent = artifact.summary || "";

      const controls = document.createElement("div"); controls.className = "artifact-controls";
      controls.dataset.busy = String(state.artifactBusy);
      const approve = document.createElement("button"); approve.type = "button"; approve.className = "action-button action-button-blue"; approve.dataset.decision = "approve"; approve.textContent = translate("actions.approve");
      const reject = document.createElement("button"); reject.type = "button"; reject.className = "action-button"; reject.dataset.decision = "reject"; reject.textContent = translate("artifacts.reject");
      const rejectWithFeedback = document.createElement("button"); rejectWithFeedback.type = "button"; rejectWithFeedback.className = "action-button"; rejectWithFeedback.dataset.decision = "reject_with_feedback"; rejectWithFeedback.textContent = translate("artifacts.rejectWithFeedback");
      controls.append(approve, reject, rejectWithFeedback);

      card.append(heading, validation, summary, controls);
      card.hidden = !isOperator;
      list.append(card);
    });
  }

  async function submitArtifactDecision(button) {
    if (state.artifactBusy || state.busy) return;
    const card = button.closest(".artifact-card");
    if (!card) return;
    const artifactId = card.dataset.artifactId;
    const version = parseInt(card.dataset.version || "0", 10);
    const action = button.dataset.decision;
    if (action === "reject_with_feedback") {
      state.feedbackTarget = { artifact_id: artifactId, version };
      $("artifact-feedback-copy").textContent = translate("artifacts.feedbackCopy", {
        artifact: artifactId, stage: card.querySelector(".artifact-stage")?.textContent || "",
      });
      $("artifact-feedback").value = "";
      $("artifact-feedback-dialog").showModal();
      return;
    }
    await sendDecision(artifactId, version, action, "");
  }

  async function sendDecision(artifactId, version, action, feedback) {
    state.artifactBusy = true; renderArtifacts(state.artifacts);
    setBusy(true);
    message(translate("messages.working"));
    try {
      await api(`/api/runs/${encodeURIComponent(state.selected)}/artifacts/${encodeURIComponent(artifactId)}/decisions`, {
        method: "POST", headers: csrfHeaders(),
        body: JSON.stringify({ artifact_version: version, action, feedback: feedback || undefined }),
      });
      message(translate("messages.actionAccepted"));
      await refresh();
    } catch (error) {
      if (String(error.message || "").toLowerCase().includes("stale")) message(translate("artifacts.stale"), true);
      else message(error.message, true);
    } finally {
      state.artifactBusy = false; setBusy(false); renderArtifacts(state.artifacts);
    }
  }
  async function login(event) { event.preventDefault(); $("login-error").textContent = ""; try { await api("/api/login", { method: "POST", body: JSON.stringify({ username: $("username").value, password: $("password").value }) }); state.me = await api("/api/me"); $("identity-label").textContent = `${state.me.username} · ${state.me.role}`; show("login-view", false); show("console-view", true); await refresh(); startPolling(); } catch (error) { $("login-error").textContent = error.message; } }
  function startPolling() { if (!state.timer) state.timer = setInterval(() => { if (!document.hidden && !state.busy) refresh(); }, 2000); }
  function stopPolling() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }

  $("login-form").addEventListener("submit", login);
  document.querySelectorAll(".language-button").forEach((button) => button.addEventListener("click", () => applyLocale(button.dataset.locale)));
  $("run-search").addEventListener("input", renderRuns);
  $("run-list").addEventListener("click", (event) => { const button = event.target.closest("button[data-run-id]"); if (button) { state.selected = button.dataset.runId; refresh(); } });
  $("pause-button").addEventListener("click", () => mutate(`/api/runs/${state.selected}/pause`));
  $("resume-button").addEventListener("click", () => mutate(`/api/runs/${state.selected}/resume`));
  $("approve-button").addEventListener("click", () => $("approval-dialog").showModal());
  $("approval-cancel").addEventListener("click", () => $("approval-dialog").close());
  $("approval-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await mutate(`/api/runs/${state.selected}/approve`, { gate: $("approval-gate").value, batch_label: $("batch-label").value }); $("approval-dialog").close(); } catch (_) {} });
  $("kill-button").addEventListener("click", () => { $("kill-confirmation").textContent = translate("messages.terminateConfirm", { run: state.selected }); $("kill-dialog").showModal(); });
  $("kill-confirm").addEventListener("click", async (event) => { event.preventDefault(); try { await mutate(`/api/runs/${state.selected}/kill`); $("kill-dialog").close(); } catch (_) {} });
  $("logout-button").addEventListener("click", async () => { try { await mutate("/api/logout"); } finally { stopPolling(); state.me = null; show("console-view", false); show("login-view", true); } });
  $("new-run-button").addEventListener("click", () => message(translate("messages.newRun")));
  $("artifact-list").addEventListener("click", (event) => { const button = event.target.closest("button[data-decision]"); if (button) submitArtifactDecision(button); });
  $("artifact-feedback-cancel").addEventListener("click", () => $("artifact-feedback-dialog").close());
  $("artifact-feedback-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const target = state.feedbackTarget; state.feedbackTarget = null;
    $("artifact-feedback-dialog").close();
    if (target) await sendDecision(target.artifact_id, target.version, "reject_with_feedback", $("artifact-feedback").value);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopPolling(); else if (state.me) { refresh(); startPolling(); } });

  applyLocale(localStorage.getItem("rockbase-console-locale") || "en");
  api("/api/me").then((me) => { state.me = me; $("identity-label").textContent = `${me.username} · ${me.role}`; show("login-view", false); show("console-view", true); refresh(); startPolling(); }).catch(() => show("login-view", true));
})();
