(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { me: null, runs: [], selected: null, timer: null };
  const api = async (path, options = {}) => {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    return payload;
  };
  const show = (id, visible) => { $(id).hidden = !visible; };
  const message = (text, error = false) => { $("action-message").textContent = text; $("action-message").className = error ? "action-message error" : "action-message"; };

  function renderRuns() {
    const list = $("run-list"); list.textContent = "";
    state.runs.forEach((run) => {
      const item = document.createElement("li"); const button = document.createElement("button");
      button.className = `run-item${run.run_id === state.selected ? " selected" : ""}`;
      button.type = "button"; button.dataset.runId = run.run_id;
      const id = document.createElement("strong"); id.textContent = run.run_id;
      const status = document.createElement("small"); status.textContent = run.status || "unknown";
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
      const stageStatus = document.createElement("span"); stageStatus.className = "stage-status"; stageStatus.textContent = record.status || "pending";
      item.append(stageName, stageStatus); timeline.append(item);
    });
    const current = entries.find(([, record]) => ["running", "retrying", "paused"].includes(record.status)) || entries[entries.length - 1];
    $("current-stage").textContent = current ? `${current[0]} · ${current[1].status || "pending"}` : "No stages recorded";
    $("stage-output").textContent = current ? [current[1].stdout, current[1].stderr].filter(Boolean).join("\n") : "";
  }
  function renderRun(run) {
    $("selected-run-title").textContent = run ? run.run_id : "No run selected";
    $("run-status").textContent = run?.status || ""; renderStages(run);
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
  async function mutate(path, body = {}) { const result = await api(path, { method: "POST", headers: csrfHeaders(), body: JSON.stringify(body) }); message("Action accepted"); await refresh(); return result; }
  async function login(event) { event.preventDefault(); $("login-error").textContent = ""; try { await api("/api/login", { method: "POST", body: JSON.stringify({ username: $("username").value, password: $("password").value }) }); state.me = await api("/api/me"); $("identity-label").textContent = `${state.me.username} · ${state.me.role}`; show("login-view", false); show("console-view", true); await refresh(); startPolling(); } catch (error) { $("login-error").textContent = error.message; } }
  function startPolling() { if (!state.timer) state.timer = setInterval(() => { if (!document.hidden) refresh(); }, 2000); }
  function stopPolling() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }
  $("login-form").addEventListener("submit", login);
  $("run-list").addEventListener("click", (event) => { const button = event.target.closest("button[data-run-id]"); if (button) { state.selected = button.dataset.runId; refresh(); } });
  $("pause-button").addEventListener("click", () => mutate(`/api/runs/${state.selected}/pause`));
  $("resume-button").addEventListener("click", () => mutate(`/api/runs/${state.selected}/resume`));
  $("approve-button").addEventListener("click", () => $("approval-dialog").showModal());
  $("approval-cancel").addEventListener("click", () => $("approval-dialog").close());
  $("approval-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await mutate(`/api/runs/${state.selected}/approve`, { gate: $("approval-gate").value, batch_label: $("batch-label").value }); $("approval-dialog").close(); } catch (error) { message(error.message, true); } });
  $("kill-button").addEventListener("click", () => { $("kill-confirmation").textContent = `Terminate ${state.selected}? This cannot be undone.`; $("kill-dialog").showModal(); });
  $("kill-confirm").addEventListener("click", async (event) => { event.preventDefault(); try { await mutate(`/api/runs/${state.selected}/kill`); $("kill-dialog").close(); } catch (error) { message(error.message, true); } });
  $("logout-button").addEventListener("click", async () => { try { await mutate("/api/logout"); } finally { stopPolling(); state.me = null; show("console-view", false); show("login-view", true); } });
  $("new-run-button").addEventListener("click", () => message("Use the API start form to define a batch."));
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopPolling(); else if (state.me) { refresh(); startPolling(); } });
  api("/api/me").then((me) => { state.me = me; $("identity-label").textContent = `${me.username} · ${me.role}`; show("login-view", false); show("console-view", true); refresh(); startPolling(); }).catch(() => show("login-view", true));
})();
