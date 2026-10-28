import {
  assignmentImpactText,
  loadAgentAssignmentImpact,
} from "./assignment-preview.mjs";

export function mountProviderConnections({
  documentRef = globalThis.document,
  fetchImpl = globalThis.fetch,
  confirmImpl = globalThis.confirm ?? (() => false),
} = {}) {
  const el = id => documentRef.getElementById(id);
  const kind = el("connection-type");
  const connectionSelect = el("assignment-provider");
  const modelSelect = el("assignment-model");
  const agentSelect = el("assignment-agent");
  const state = el("connection-state");
  const key = el("connection-key");
  const url = el("connection-url");
  let connections = [];
  let agents = [];
  let busy = false;
  let canManage = false;
  let canManageRuntime = false;
  let runtimeEvidence = null;

  function option(select, value, label) {
    const item = documentRef.createElement("option");
    item.value = value;
    item.textContent = label;
    select.append(item);
  }

  function controls() {
    const selected = connections.find(item => item.provider_id === connectionSelect.value);
    const slots = el("connection-slots");
    const gemini = kind.value === "gemini";
    const compatible = ["openai-compatible", "free-pool"].includes(kind.value) || selected?.provider_type==="openai-compatible";
    if(el("endpoint-options")) el("endpoint-options").hidden=!compatible;
    for(const id of ["endpoint-test","endpoint-save"]) if(el(id)) {
      el(id).hidden=selected?.provider_type!=="openai-compatible";
      el(id).disabled=busy || !canManage;
    }
    el("connection-url-field").hidden = gemini;
    el("connection-key-field").hidden = !gemini && !compatible;
    slots.disabled = busy || gemini || compatible;
    if (gemini || compatible) slots.value = "1";
    el("connection-add").textContent=["openai-compatible","free-pool"].includes(kind.value) ? "Add cloud connection (Test separately)" : "Add and verify connection";
    el("connection-add").disabled = busy || !canManage;
    el("connection-refresh").disabled = busy || !selected || !canManage || selected?.provider_type==="openai-compatible";
    el("connection-remove").disabled = busy || !selected || !canManage;
    connectionSelect.disabled = busy || !connections.length;
    modelSelect.disabled = busy || !selected || !selected.models.length;
    agentSelect.disabled = busy || !agents.length;
    el("assignment-save").disabled = busy || !selected || !modelSelect.value || !agentSelect.value || !canManage;
    const runtimeSupported = selected?.provider_type === "ollama";
    el("model-runtime-refresh").disabled = busy || !selected;
    el("model-load").disabled = busy || !canManageRuntime || !runtimeSupported || !modelSelect.value;
    el("model-unload").disabled = busy || !canManageRuntime || !runtimeSupported || !modelSelect.value;
  }

  async function request(path, { method = "GET", body } = {}) {
    const options = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
    if (method !== "GET") {
      const sessionResponse = await fetchImpl("/api/local/session", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!sessionResponse.ok) throw new Error("Sign in through local owner access first.");
      const session = await sessionResponse.json();
      options.headers = {
        ...options.headers,
        "Content-Type": "application/json",
        "X-Local-CSRF": session.csrf,
      };
      options.body = JSON.stringify(body ?? {});
    }
    const response = await fetchImpl(path, options);
    let data = {};
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sign in through local owner access first.");
      if (response.status === 403) throw new Error("This session lacks provider-connection permission.");
      throw new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "Provider connection request failed.");
    }
    return data;
  }

  function renderConnections() {
    connectionSelect.replaceChildren();
    el("connection-list").replaceChildren();
    for (const item of connections) {
      if (!item || typeof item.provider_id !== "string" || !Array.isArray(item.models)) {
        throw new Error("Provider connection response was invalid.");
      }
      option(
        connectionSelect,
        item.provider_id,
        `${item.name} · ${item.provider_id} · ${item.provider_type}`,
      );
      const row = documentRef.createElement("li");
      row.textContent =
        `${item.name} (${item.provider_id}) · ${item.provider_type} · ${item.state} · ` +
        `${item.models.length} catalog model(s) · ${item.request_capacity.provider_slots ?? "UNKNOWN"} request slot(s) · ` +
        "hardware feasibility UNKNOWN";
      el("connection-list").append(row);
    }
    renderModels();
  }

  function renderModels() {
    const current = connections.find(item => item.provider_id === connectionSelect.value);
    if(current?.endpoint) {
      if(el("endpoint-enabled"))el("endpoint-enabled").checked=current.endpoint.enabled===true;
      if(el("endpoint-brain"))el("endpoint-brain").checked=current.endpoint.allow_brain_context===true;
    }
    runtimeEvidence = null;
    el("model-runtime-state").textContent = "";
    el("model-runtime-evidence").textContent = "";
    modelSelect.replaceChildren();
    if (current) {
      for (const model of current.models) option(modelSelect, model, model);
    }
    state.textContent = current
      ? `${current.name}: ${current.state}; catalog source ${current.source}; checked ${current.checked_at ?? "unknown"}.`
      : connections.length
        ? "Choose a provider connection."
        : "No additional provider connections are configured.";
    if(current?.endpoint)state.textContent=`${current.name}: ${current.endpoint.state_label}; cloud turns ${current.endpoint.enabled ? "enabled" : "off"}; Brain context ${current.endpoint.allow_brain_context ? "allowed with preview" : "off"}.`;
    controls();
  }

  function showRuntime(observation) {
    runtimeEvidence = observation;
    const runtime = observation.runtime;
    const loaded = Array.isArray(runtime.models) ? runtime.models : [];
    const rows = loaded.map(model => {
      const size = model.size_bytes === null ? "unknown" : `${model.size_bytes} bytes`;
      const vram = model.vram_bytes === null ? "unknown" : `${model.vram_bytes} bytes`;
      return `${model.name} · memory ${size} · VRAM ${vram} · context ${model.context_length ?? "unknown"}`;
    });
    el("model-runtime-evidence").textContent = [
      `Loaded models (${runtime.state}): ${rows.length ? rows.join("; ") : "none reported"}`,
      `Runtime probe latency: ${runtime.probe_latency_ms === null ? "unknown" : `${runtime.probe_latency_ms.toFixed(2)} ms`} (not inference latency)`,
      `Request slots: ${observation.request_capacity.provider_slots ?? "UNKNOWN"} provider / ${observation.request_capacity.global_slots ?? "UNKNOWN"} global; active requests ${observation.request_capacity.active_requests ?? "unknown"}`,
      `Hardware feasibility: ${observation.hardware_feasibility}; inference latency: ${observation.inference_latency}`,
      runtime.reason ?? "",
    ].filter(Boolean).join("\n");
    el("model-runtime-state").textContent = runtime.supported
      ? "Runtime status is provider-reported. A listed model is loaded once per provider/model, regardless of how many Agents share its assignment."
      : "This provider does not expose supported loaded-model telemetry or lifecycle controls.";
    controls();
  }

  async function refresh() {
    const sessionResponse = await request("/api/local/session");
    canManage = sessionResponse.permissions.includes("provider-connection:manage");
    const [agentResult, connectionResult] = await Promise.all([
      request("/api/agents"),
      request("/api/local/provider-connections"),
    ]);
    if (!Array.isArray(agentResult.items) || !Array.isArray(connectionResult.items)) {
      throw new Error("Provider connection response was invalid.");
    }
    agents = agentResult.items;
    connections = connectionResult.items;
    canManageRuntime = sessionResponse.permissions.includes("model-runtime:manage");
    agentSelect.replaceChildren();
    for (const agent of agents) {
      option(agentSelect, agent.id, `${agent.name} · ${agent.provider}/${agent.model}`);
    }
    renderConnections();
    controls();
  }

  async function run(action) {
    if (busy) return false;
    busy = true;
    controls();
    try {
      await action();
      return true;
    } catch (error) {
      state.textContent = error.message;
      return false;
    } finally {
      busy = false;
      controls();
    }
  }

  async function add() {
    return run(async () => {
      const common = {
        id: el("connection-id").value,
        name: el("connection-name").value,
        request_slots: Number(el("connection-slots").value),
      };
      state.textContent = ["openai-compatible","free-pool"].includes(kind.value) ? "Saving configuration in memory; no network call is made by Add." : "Verifying the explicitly selected provider connection…";
      try {
        if (["openai-compatible","free-pool"].includes(kind.value)) {
          const base=url.value;
          let remote=false;
          try { remote=!["127.0.0.1","localhost","[::1]"].includes(new URL(base).hostname); }
          catch { throw new Error("Enter a valid endpoint URL ending in /v1."); }
          if(remote && !confirmImpl(`Send future approved requests and this key to ${base}? Non-loopback URLs require HTTPS; HTTP can expose prompts and keys. Your prompt may be sent to any provider enabled in that router.`)) {state.textContent="Remote connection cancelled. No endpoint request was sent.";return;}
          await request("/api/local/provider-connections/openai-compatible",{method:"POST",body:{id:common.id,name:common.name,base_url:base,api_key:key.value,
            remote_confirmed:remote,preset:kind.value==="free-pool",enabled:el("endpoint-enabled")?.checked===true,allow_brain_context:el("endpoint-brain")?.checked===true}});
        } else if (kind.value === "gemini") {
          await request("/api/local/provider-connections/gemini", {
            method: "POST",
            body: { ...common, api_key: key.value },
          });
        } else {
          await request("/api/local/provider-connections/ollama", {
            method: "POST",
            body: { ...common, base_url: url.value },
          });
        }
      } finally {
        key.value = "";
      }
      el("connection-id").value = "";
      el("connection-name").value = "";
      await refresh();
      state.textContent = "Connection saved in memory for this app run. Hardware feasibility remains UNKNOWN.";
    });
  }

  async function refreshSelected() {
    return run(async () => {
      if (!connectionSelect.value) return;
      await request(`/api/local/provider-connections/${encodeURIComponent(connectionSelect.value)}/refresh`, {
        method: "POST",
      });
      await refresh();
      state.textContent = "Provider catalog/status refreshed from its configured source.";
    });
  }

  async function refreshRuntime() {
    return run(async () => {
      if (!connectionSelect.value) return;
      el("model-runtime-state").textContent = "Checking provider-reported loaded-model status…";
      const observation = await request(
        `/api/local/provider-connections/${encodeURIComponent(connectionSelect.value)}/runtime`,
      );
      showRuntime(observation);
    });
  }

  async function manageModel(action) {
    return run(async () => {
      const selected = connections.find(item => item.provider_id === connectionSelect.value);
      const model = modelSelect.value;
      if (!selected || !model) return;
      if (action === "unload" && !runtimeEvidence) {
        throw new Error("Refresh runtime status before unloading a model.");
      }
      const warning = action === "load"
        ? `Load ${model} on ${selected.provider_id} for ${el("model-keep-alive").value} seconds of idle time? This model may be shared by multiple Agents. Hardware fit is UNKNOWN; the local runtime may reject the request. No prompt is sent.`
        : `Unload shared model ${model} from ${selected.provider_id}? Active requests block unloading. Agents assigned this model may need it loaded again.`;
      if (!confirmImpl(warning)) {
        el("model-runtime-state").textContent = `Model ${action} cancelled; provider state is unchanged.`;
        return;
      }
      const path = `/api/local/provider-connections/${encodeURIComponent(selected.provider_id)}/models/${action}`;
      const result = await request(path, {
        method: "POST",
        body: { model_id: model, keep_alive_seconds: Number(el("model-keep-alive").value) },
      });
      showRuntime(result);
      el("model-runtime-state").textContent =
        `${action === "load" ? "Load" : "Unload"} requested for ${model}; operation took ${result.operation_latency_ms.toFixed(2)} ms. Hardware feasibility remains UNKNOWN.`;
    });
  }

  async function removeSelected() {
    return run(async () => {
      const selected = connections.find(item => item.provider_id === connectionSelect.value);
      if (!selected || !confirmImpl(
        `Remove ${selected.name} (${selected.provider_id}) and erase its in-memory credentials? ` +
        "Agents must be reassigned first; existing conversations retain their snapshots.",
      )) return;
      await request(`/api/local/provider-connections/${encodeURIComponent(selected.provider_id)}`, {
        method: "DELETE",
      });
      await refresh();
      state.textContent = "Provider connection removed and its in-memory credential erased.";
    });
  }

  async function assign() {
    return run(async () => {
      const agent = agents.find(item => item.id === agentSelect.value);
      const selected = connections.find(item => item.provider_id === connectionSelect.value);
      if (!agent || !selected || !modelSelect.value) return;
      const impact = await loadAgentAssignmentImpact(agent.id, fetchImpl);
      const dataPrivacy = selected.provider_type === "openai-compatible"
        ? "Cloud: your prompt may be sent to any provider enabled in that router. Every turn requires an exact outbound preview and fresh approval."
        : selected.provider_type === "gemini"
        ? "Future chat turns and recent history are sent to Google only after separate per-turn consent."
        : "Requests are sent only to the configured loopback Ollama service.";
      const preview = [
        `Change ${agent.name} (${agent.id}) from ${agent.provider}/${agent.model} to ${selected.provider_id}/${modelSelect.value}?`,
        dataPrivacy,
        `Connection request slots: ${selected.request_capacity.provider_slots ?? "UNKNOWN"}. Hardware feasibility: UNKNOWN.`,
        assignmentImpactText(impact),
      ].join("\n\n");
      if (!confirmImpl(preview)) {
        state.textContent = "Assignment unchanged; the preview was cancelled.";
        return;
      }
      await request("/api/local/provider-connections/assignment", {
        method: "PUT",
        body: {
          agent_id: agent.id,
          provider_id: selected.provider_id,
          model_id: modelSelect.value,
          expected_provider_id: agent.provider,
          expected_model_id: agent.model,
        },
      });
      await refresh();
      state.textContent = "Agent assignment updated. Existing conversations keep their snapshots; start a new conversation to use it.";
    });
  }

  kind.addEventListener("change", () => {
    if(kind.value==="free-pool") {
      url.value="http://127.0.0.1:3001/v1";
      el("connection-name").value="Free pool (FreeLLMAPI)";
      el("connection-id").value="free-pool";
    }
    controls();
  });
  el("endpoint-test")?.addEventListener("click",()=>run(async()=>{
    const selected=connections.find(item=>item.provider_id===connectionSelect.value);
    if(!selected || !confirmImpl("Test sends the fixed text Hi with a one-token limit. Your prompt may be sent to any provider enabled in that router. Its upstream costs and retries are unknown. Continue?"))return;
    const body={consent:true};
    if(!selected.endpoint.experimental && modelSelect.value)body.model_id=modelSelect.value;
    const result=await request(`/api/local/provider-connections/${encodeURIComponent(selected.provider_id)}/test`,{method:"POST",body});
    await refresh();state.textContent=result.test.state_label+". "+(result.test.message || "Test completed; served model is known only when the router reports it.");
  }));
  el("endpoint-save")?.addEventListener("click",()=>run(async()=>{
    const selected=connections.find(item=>item.provider_id===connectionSelect.value);
    if(!selected || !confirmImpl("Apply these cloud settings to "+selected.name+"? Every generation still requires exact preview approval."))return;
    await request(`/api/local/provider-connections/${encodeURIComponent(selected.provider_id)}/privacy`,{method:"PATCH",body:{enabled:el("endpoint-enabled").checked,allow_brain_context:el("endpoint-brain").checked}});
    await refresh();state.textContent="Cloud privacy settings saved for this app run.";
  }));
  connectionSelect.addEventListener("change", renderModels);
  modelSelect.addEventListener("change", controls);
  agentSelect.addEventListener("change", controls);
  el("connection-add").addEventListener("click", add);
  el("connection-refresh").addEventListener("click", refreshSelected);
  el("model-runtime-refresh").addEventListener("click", refreshRuntime);
  el("model-load").addEventListener("click", () => manageModel("load"));
  el("model-unload").addEventListener("click", () => manageModel("unload"));
  el("connection-remove").addEventListener("click", removeSelected);
  el("assignment-save").addEventListener("click", assign);
  controls();
  if(globalThis.location?.hash==="#free-pool") {
    kind.value="free-pool";url.value="http://127.0.0.1:3001/v1";el("connection-id").value="free-pool";el("connection-name").value="Free pool (FreeLLMAPI)";controls();
  }
  return { initialLoad: run(refresh), add, assign, refresh, refreshSelected, refreshRuntime, manageModel, removeSelected };
}

if (typeof document !== "undefined" && document.getElementById("connection-type")) {
  mountProviderConnections();
}
