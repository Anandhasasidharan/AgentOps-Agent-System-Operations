(function () {
  "use strict";
  const { el, badge, eventRow } = AgentOpsRender;
  const $ = (id) => document.getElementById(id);
  const names = {
    overview: "Overview",
    agents: "Agents",
    calls: "Execution log",
    policies: "Policies",
    incidents: "Incidents",
    slos: "Reliability",
    chaos: "Chaos lab",
    events: "Live events",
    settings: "Workspace & reports",
  };
  const state = {
    data: {},
    health: null,
    errors: [],
    page: "overview",
    search: "",
    filter: "all",
    tab: "scenarios",
    events: [],
    eventIds: new Set(),
    busy: false,
    live: false,
    updated: null,
  };
  const list = (key) => (Array.isArray(state.data[key]) ? state.data[key] : []);
  const short = (value) => (value ? String(value).slice(0, 8) : "—");
  const number = (value) =>
    Number.isFinite(Number(value))
      ? Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
      : "—";
  const percent = (value) =>
    value === null || value === undefined ? "—" : (Number(value) * 100).toFixed(1) + "%";
  const date = (value) =>
    value
      ? new Date(value).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "—";
  const ago = (value) => {
    if (!value) return "—";
    const n = Math.max(0, Math.floor((Date.now() - new Date(value)) / 60000));
    return n < 1
      ? "just now"
      : n < 60
        ? n + "m ago"
        : n < 1440
          ? Math.floor(n / 60) + "h ago"
          : Math.floor(n / 1440) + "d ago";
  };
  const agentName = (id) => list("agents").find((a) => a.id === id)?.name || short(id);
  const btn = (text, action, tone = "", small = false) =>
    el("button", {
      type: "button",
      class: "button " + tone + (small ? " small" : ""),
      text,
      onclick: action,
    });
  const actions = (children) => el("div", { class: "cell-actions" }, children);
  function toast(message, error = false) {
    const node = el("div", { class: "toast" + (error ? " error" : ""), text: message });
    $("toast-region").append(node);
    setTimeout(() => node.remove(), 6000);
  }
  function errorMessage(value) {
    if (Array.isArray(value))
      return value.map((v) => (v.loc || []).slice(1).join(".") + ": " + v.msg).join("\n");
    return typeof value === "string" ? value : JSON.stringify(value);
  }
  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (response.status === 204) return null;
    const type = response.headers.get("content-type") || "";
    const value = type.includes("json") ? await response.json() : await response.text();
    if (!response.ok)
      throw new Error(
        response.status === 401
          ? "Your session expired. Reload and sign in."
          : errorMessage(value?.detail || value || "Operation failed"),
      );
    return value;
  }
  const api = (service, path, body, method = body === undefined ? "GET" : "POST") =>
    fetchJSON("/api/services/" + service + "/" + path, {
      method,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  function addEvents(events) {
    for (const event of events || []) {
      const id = event.event_id || JSON.stringify(event);
      if (!state.eventIds.has(id)) {
        state.eventIds.add(id);
        state.events.push(event);
      }
    }
    state.events.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    state.events = state.events.slice(0, 500);
    state.eventIds = new Set(state.events.map((e) => e.event_id || JSON.stringify(e)));
  }
  async function refresh() {
    if (state.busy) {
      state.reload = true;
      return;
    }
    state.busy = true;
    $("refresh").disabled = true;
    try {
      const [snapshot, health] = await Promise.all([
        fetchJSON("/api/snapshot"),
        fetchJSON("/api/health"),
      ]);
      for (const [key, value] of Object.entries(snapshot.data))
        if (value !== null) state.data[key] = value;
      state.errors = snapshot.errors;
      state.health = health;
      addEvents(snapshot.data.events);
      state.updated = new Date();
      $("tenant-name").textContent = state.data.tenant?.name || "Tenant workspace";
      $("nav-agents").textContent = state.data.agents ? list("agents").length : "—";
      $("nav-incidents").textContent = state.data.incidents ? list("incidents").length : "—";
      $("system-label").textContent =
        health.status === "ok" && !snapshot.errors.length
          ? "All systems operational"
          : "Some services degraded";
      $("system-dot").className =
        "dot" + (health.status === "ok" && !snapshot.errors.length ? "" : " error");
      const notice = $("global-error");
      notice.hidden = !state.errors.length;
      notice.textContent = state.errors.length
        ? "Some data could not be refreshed. Last available data is retained. " +
          state.errors.join(" · ")
        : "";
      $("last-updated").textContent =
        "Updated " +
        state.updated.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
      render();
    } catch (error) {
      $("global-error").hidden = false;
      $("global-error").textContent = error.message;
      if (!state.updated) {
        $("main").replaceChildren(
          el("div", { class: "loading-state" }, [
            el("h2", { text: "Workspace unavailable" }),
            el("p", { text: error.message }),
            btn("Try again", refresh, "primary"),
          ]),
        );
      }
    } finally {
      state.busy = false;
      $("refresh").disabled = false;
      if (state.reload) {
        state.reload = false;
        setTimeout(refresh, 0);
      }
    }
  }
  function heading(title, description, buttons = []) {
    return el("div", { class: "page-heading" }, [
      el("div", {}, [el("h1", { text: title }), el("p", { text: description })]),
      el("div", { class: "page-actions" }, buttons),
    ]);
  }
  function panel(title, subtitle, content, extra) {
    return el("section", { class: "panel" }, [
      el("div", { class: "panel-header" }, [
        el("div", {}, [el("h2", { text: title }), subtitle ? el("p", { text: subtitle }) : null]),
        extra || null,
      ]),
      content,
    ]);
  }
  function empty(title, description, button) {
    return el("div", { class: "empty" }, [
      el("span", { class: "empty-symbol", text: "◇" }),
      el("strong", { text: title }),
      el("p", { text: description }),
      button || null,
    ]);
  }
  function metric(label, value, caption, icon = "◇") {
    return el("div", { class: "metric" }, [
      el("div", { class: "metric-top" }, [
        el("span", { text: label }),
        el("span", { class: "metric-icon", text: icon }),
      ]),
      el("div", { class: "metric-value", text: value }),
      el("div", { class: "metric-caption", text: caption }),
    ]);
  }
  function notice(text) {
    return el("div", { class: "notice", text });
  }
  function table(
    headers,
    rows,
    emptyTitle = "No records yet",
    emptyText = "New records will appear here.",
    toolbar,
  ) {
    return el("section", { class: "panel" }, [
      toolbar || null,
      rows.length
        ? el("div", { class: "table-wrap" }, [
            el("table", {}, [
              el("thead", {}, [
                el(
                  "tr",
                  {},
                  headers.map((h) => el("th", { scope: "col", text: h })),
                ),
              ]),
              el(
                "tbody",
                {},
                rows.map((cells) =>
                  el(
                    "tr",
                    {},
                    cells.map((cell) =>
                      el("td", {}, [typeof cell === "string" ? el("span", { text: cell }) : cell]),
                    ),
                  ),
                ),
              ),
            ]),
          ])
        : empty(emptyTitle, emptyText),
      el("div", { class: "table-footer" }, [
        el("span", { text: rows.length + " record" + (rows.length === 1 ? "" : "s") }),
        el("span", { text: "Live workspace data" }),
      ]),
    ]);
  }
  function searchToolbar(placeholder, options) {
    const input = el("input", {
      id: "table-search",
      class: "search-input",
      type: "search",
      placeholder,
      value: state.search,
      "aria-label": placeholder,
      oninput: (e) => {
        state.search = e.target.value;
        render();
      },
    });
    const children = [input];
    if (options) {
      const select = el(
        "select",
        {
          class: "filter-select",
          "aria-label": "Filter records",
          onchange: (e) => {
            state.filter = e.target.value;
            render();
          },
        },
        options.map(([value, label]) =>
          el("option", { value, text: label, selected: state.filter === value }),
        ),
      );
      children.push(select);
    }
    return el("div", { class: "table-toolbar" }, children);
  }
  function matches(value) {
    return (
      !state.search || JSON.stringify(value).toLowerCase().includes(state.search.toLowerCase())
    );
  }
  function identity(name, id) {
    return el("div", { class: "agent-cell" }, [
      el("span", {
        class: "agent-avatar",
        text: String(name || "?")
          .slice(0, 2)
          .toUpperCase(),
      }),
      el("div", {}, [
        el("strong", { text: name || "Unnamed" }),
        el("small", { class: "mono", text: id }),
      ]),
    ]);
  }
  function jsonView(value) {
    return el("pre", { class: "json-view", text: JSON.stringify(value, null, 2) });
  }
  function detail(title, value, description = "") {
    openModal(title, [
      description ? el("p", { class: "modal-description", text: description }) : null,
      jsonView(value),
    ]);
  }
  function openModal(title, children) {
    $("modal-title").textContent = title;
    $("modal-content").replaceChildren(el("div", { class: "modal-body" }, children));
    if (!$("modal").open) $("modal").showModal();
  }
  function closeModal() {
    if (!$("modal").dataset.busy) $("modal").close();
  }
  function fieldNode(field) {
    let control;
    if (field.options) {
      control = el(
        "select",
        {
          name: field.name,
          id: "form-" + field.name,
          required: !!field.required,
          multiple: !!field.multiple,
        },
        field.options.map((option) => {
          const [value, label] = Array.isArray(option) ? option : [option, option];
          return el("option", {
            value,
            text: label,
            selected: String(field.value ?? "") === String(value),
          });
        }),
      );
    } else {
      control = el(field.type === "textarea" ? "textarea" : "input", {
        name: field.name,
        id: "form-" + field.name,
        type: field.type === "textarea" ? null : field.type || "text",
        placeholder: field.placeholder || "",
        required: !!field.required,
        value: field.value ?? "",
        ...(field.type === "number"
          ? { min: field.min ?? 0, max: field.max, step: field.step ?? "any" }
          : {}),
      });
      if (field.type === "textarea") control.textContent = field.value || "";
    }
    control.setAttribute("aria-label", field.label);
    if (field.required) control.required = true;
    return {
      wrapper: el("label", { class: "field" + (field.full ? " full" : "") }, [
        el("span", { text: field.label }),
        control,
        field.help ? el("small", { text: field.help }) : null,
      ]),
      control,
    };
  }
  function openForm(title, description, fields, onSubmit, submit = "Create", danger = false) {
    $("modal-title").textContent = title;
    const grid = el("div", { class: "form-grid" });
    const controls = {};
    for (const field of fields) {
      const { wrapper, control } = fieldNode(field);
      grid.append(wrapper);
      controls[field.name] = control;
    }
    const error = el("div", { class: "form-error", role: "alert" });
    const submitButton = el("button", {
      class: "button " + (danger ? "danger" : "primary"),
      type: "submit",
      text: submit,
    });
    const cancel = btn("Cancel", closeModal, "ghost");
    const form = el("form", {}, [
      el("div", { class: "modal-body" }, [
        el("p", { class: "modal-description", text: description }),
        grid,
        error,
      ]),
      el("div", { class: "modal-footer" }, [cancel, submitButton]),
    ]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      error.textContent = "";
      submitButton.disabled = true;
      cancel.disabled = true;
      $("modal").dataset.busy = "1";
      const original = submitButton.textContent;
      submitButton.textContent = "Working…";
      try {
        const values = {};
        for (const field of fields) {
          values[field.name] = field.multiple
            ? Array.from(controls[field.name].selectedOptions).map((o) => o.value)
            : controls[field.name].value;
        }
        const result = await onSubmit(values, controls);
        delete $("modal").dataset.busy;
        $("modal").close();
        toast("Operation completed");
        await refresh();
        if (result !== undefined) detail(title + " · result", result);
      } catch (exc) {
        error.textContent = exc.message;
      } finally {
        delete $("modal").dataset.busy;
        submitButton.disabled = false;
        cancel.disabled = false;
        submitButton.textContent = original;
      }
    });
    $("modal-content").replaceChildren(form);
    if (!$("modal").open) $("modal").showModal();
    setTimeout(() => Object.values(controls)[0]?.focus(), 30);
  }
  const json = (text, label = "JSON") => {
    try {
      return JSON.parse(text || "{}");
    } catch {
      throw new Error(label + " must be valid JSON.");
    }
  };
  const agentOptions = () => list("agents").map((a) => [a.id, a.name + " · " + short(a.id)]);
  function requireAgents() {
    if (!list("agents").length) {
      toast("Register an agent first.", true);
      createAgent();
      return false;
    }
    return true;
  }
  function createAgent() {
    openForm(
      "Register an agent",
      "Register the identity used in tool calls and agent-scoped reliability objectives.",
      [
        {
          name: "name",
          label: "Agent name",
          required: true,
          placeholder: "customer-support-agent",
          full: true,
        },
        {
          name: "environment",
          label: "Environment",
          value: "production",
          options: ["production", "staging", "development"],
        },
        { name: "framework", label: "Framework", placeholder: "LangChain, custom…" },
        { name: "model_provider", label: "Model provider", placeholder: "Optional", full: true },
      ],
      async (v) => {
        await api("slo", "api/v1/agents", {
          name: v.name,
          environment: v.environment,
          framework: v.framework || null,
          model_provider: v.model_provider || null,
        });
      },
      "Register agent",
    );
  }
  const conditions = {
    tool_blocklist: { tools: ["delete_database", "execute_shell"] },
    tool_allowlist: { tools: ["read_*", "search_*"] },
    rate_limit: { max_calls: 100 },
    token_budget: { max_tokens: 10000 },
    risk_threshold: { max_risk_score: 0.8 },
    anomaly_threshold: { max_anomaly_score: 0.8 },
    time_window: { start: 0, end: 6 },
    reasoning_loop: { max_consecutive_same_tool: 5 },
  };
  function createPolicy() {
    openForm(
      "Create a policy",
      "Policies are evaluated by priority, highest first. The first matching policy determines the decision.",
      [
        {
          name: "name",
          label: "Policy name",
          required: true,
          placeholder: "protect-destructive-tools",
          full: true,
        },
        {
          name: "policy_type",
          label: "Policy type",
          options: Object.keys(conditions),
          value: "tool_blocklist",
        },
        {
          name: "action",
          label: "Action",
          options: [
            ["block", "Block call"],
            ["kill", "Kill agent (persistent)"],
            ["allow", "Allow call"],
          ],
        },
        { name: "priority", label: "Priority", type: "number", value: "10", step: "1" },
        {
          name: "agent_id",
          label: "Scope",
          options: [["", "All agents in this tenant"], ...agentOptions()],
        },
        {
          name: "conditions",
          label: "Conditions",
          type: "textarea",
          value: JSON.stringify(conditions.tool_blocklist, null, 2),
          full: true,
          help: "Keys are validated by the service. Midnight windows are supported; cross-midnight windows are not.",
        },
        { name: "description", label: "Description", placeholder: "Optional", full: true },
      ],
      async (v) => {
        const cond = json(v.conditions, "Conditions");
        if (v.agent_id) cond.agent_id = v.agent_id;
        await api("breaker", "api/v1/policies", {
          name: v.name,
          policy_type: v.policy_type,
          action: v.action,
          priority: Number(v.priority),
          conditions: cond,
          description: v.description || null,
        });
      },
      "Create policy",
    );
    const select = $("form-policy_type");
    select.addEventListener("change", () => {
      $("form-conditions").value = JSON.stringify(conditions[select.value], null, 2);
    });
  }
  function deletePolicy(policy) {
    openForm(
      "Delete policy",
      "Delete “" +
        policy.name +
        "”? This removes its protection immediately. An automatic lockdown may be recreated while its SLO is still breaching.",
      [],
      async () => {
        await api(
          "breaker",
          "api/v1/policies/" + encodeURIComponent(policy.id),
          undefined,
          "DELETE",
        );
      },
      "Delete policy",
      true,
    );
  }
  function killAgent(agent) {
    openForm(
      "Activate kill switch",
      "Block every subsequent tool call for " +
        (agent?.name || "the selected agent") +
        ". Calls remain blocked until release or expiry.",
      [
        {
          name: "agent_id",
          label: "Agent",
          options: agentOptions(),
          value: agent?.id,
          required: true,
          full: true,
        },
        {
          name: "reason",
          label: "Reason",
          required: true,
          placeholder: "Describe why this agent must be stopped",
          full: true,
        },
        {
          name: "ttl",
          label: "Expires after (seconds)",
          type: "number",
          value: 3600,
          min: 1,
          step: 1,
          help: "Default: one hour. Release is available from agent inspection.",
        },
      ],
      async (v) => {
        await api(
          "breaker",
          "api/v1/kill-switch/" +
            encodeURIComponent(v.agent_id) +
            "/activate?" +
            new URLSearchParams({ reason: v.reason, ttl: v.ttl }),
          {},
        );
      },
      "Activate kill switch",
      true,
    );
  }
  async function inspectAgent(agent) {
    try {
      const [status, prediction] = await Promise.all([
        api("breaker", "api/v1/agents/" + encodeURIComponent(agent.id) + "/status"),
        api("breaker", "api/v1/predict/" + encodeURIComponent(agent.id)),
      ]);
      openModal(agent.name, [
        el("p", { class: "modal-description", text: "Agent " + agent.id }),
        el("div", { class: "pill-list" }, [
          badge(
            status.is_killed ? "Kill switch active" : "No active kill switch",
            status.is_killed ? "red" : "green",
          ),
          badge(agent.environment || "unregistered"),
        ]),
        el("div", { class: "actions" }, [
          btn(
            status.is_killed ? "Release kill switch" : "Activate kill switch",
            () =>
              status.is_killed
                ? openForm(
                    "Release kill switch",
                    "Allow this agent to make calls again. Other blocking policies still apply.",
                    [],
                    async () => {
                      await api(
                        "breaker",
                        "api/v1/kill-switch/" + encodeURIComponent(agent.id) + "/release",
                        {},
                      );
                    },
                    "Release switch",
                  )
                : killAgent(agent),
            status.is_killed ? "" : "danger",
          ),
          btn("Check a tool call", () => checkCall(agent)),
        ]),
        el("h3", { text: "Execution state", class: "section-label" }),
        jsonView(status),
        el("h3", { text: "Predictive model · experimental", class: "section-label" }),
        el("p", {
          class: "subtle",
          text: "Model estimates are not validated guarantees of real-world risk.",
        }),
        jsonView(prediction),
      ]);
    } catch (error) {
      toast(error.message, true);
    }
  }
  function checkCall(agent) {
    if (!requireAgents()) return;
    openForm(
      "Check a tool call",
      "Send an intercept request. This records a real decision and may trigger policies, incidents, kill switches, and SLOs. It does not execute the tool.",
      [
        {
          name: "agent_id",
          label: "Agent",
          options: agentOptions(),
          value: agent?.id,
          required: true,
          full: true,
        },
        {
          name: "tool_name",
          label: "Tool name",
          value: "read_inventory",
          required: true,
          full: true,
        },
        { name: "tool_input", label: "Tool input", type: "textarea", value: "{}", full: true },
        { name: "token_count", label: "Tokens", type: "number", value: 0, step: 1 },
        { name: "cost", label: "Cost", type: "number", value: 0, step: 0.001 },
      ],
      async (v) =>
        api("breaker", "v1/intercept", {
          agent_id: v.agent_id,
          tool_name: v.tool_name,
          tool_input: json(v.tool_input, "Tool input"),
          token_count: Number(v.token_count),
          cost: Number(v.cost),
        }),
      "Evaluate call",
    );
  }
  function createSLI() {
    openForm(
      "Create an indicator",
      "OTLP-derived indicators use the supported metric names shown below.",
      [
        {
          name: "name",
          label: "Metric name",
          options: [
            "tool_accuracy",
            "task_success_rate",
            "hallucination_rate",
            "latency_p99",
            "token_usage",
            "cost_per_task",
            "trust_score",
            "prompt_tokens",
            "completion_tokens",
          ],
          full: true,
        },
        {
          name: "metric_type",
          label: "Metric type",
          options: ["ratio", "threshold", "budget", "count"],
        },
        { name: "source", label: "Source", value: "otel", required: true },
      ],
      async (v) => {
        await api("slo", "api/v1/slis", { ...v, config: {} });
      },
      "Create indicator",
    );
    $("form-name").addEventListener("change", (e) => {
      $("form-metric_type").value = [
        "tool_accuracy",
        "task_success_rate",
        "hallucination_rate",
        "trust_score",
      ].includes(e.target.value)
        ? "ratio"
        : e.target.value.includes("token")
          ? "count"
          : "threshold";
    });
  }
  function importTraces() {
    openForm(
      "Import telemetry",
      "Ingest real OTLP trace JSON under this tenant. Recorded failures may trigger SLO alerts and agent lockdown.",
      [
        {
          name: "payload",
          label: "OTLP JSON",
          type: "textarea",
          value: '{\n  "resourceSpans": []\n}',
          full: true,
        },
      ],
      async (v) => api("slo", "v1/traces", json(v.payload, "OTLP payload")),
      "Ingest traces",
    );
  }
  function createSLO() {
    if (!list("slis").some((s) => s.metric_type === "ratio")) {
      toast("Create a ratio indicator first.", true);
      createSLI();
      return;
    }
    openForm(
      "Create an objective",
      "Agent-scoped objectives can trigger automatic lockdown. Use the same agent UUID in your SDK calls. Ratio objectives are the supported budget model.",
      [
        {
          name: "name",
          label: "Objective name",
          required: true,
          placeholder: "95% tool accuracy",
          full: true,
        },
        {
          name: "sli_id",
          label: "Indicator",
          options: list("slis")
            .filter((s) => s.metric_type === "ratio")
            .map((s) => [s.id, s.name]),
          required: true,
          full: true,
        },
        {
          name: "agent_id",
          label: "Agent scope",
          options: [["", "Tenant-wide (no targeted lockdown)"], ...agentOptions()],
          full: true,
        },
        {
          name: "target",
          label: "Target (0–1)",
          type: "number",
          min: 0.000001,
          max: 1,
          step: "any",
          value: 0.95,
          required: true,
        },
        {
          name: "comparator",
          label: "Condition",
          options: [
            ["gt", "At least target"],
            ["lt", "At most target"],
            ["eq", "Equal to target"],
          ],
        },
        {
          name: "window",
          label: "Rolling window",
          options: ["1h", "1d", "7d", "30d"],
          value: "7d",
        },
        { name: "description", label: "Description", placeholder: "Optional" },
      ],
      async (v) => {
        await api("slo", "api/v1/slos", {
          ...v,
          target: Number(v.target),
          agent_id: v.agent_id || null,
          description: v.description || null,
        });
      },
      "Create objective",
    );
  }
  function resolveIncident(incident) {
    openForm(
      "Resolve incident",
      "Mark this incident as resolved. Resolving an incident does not release a kill switch or remove a lockdown policy.",
      [],
      async () => {
        await api("breaker", "api/v1/incidents/" + incident.id + "/resolve", {});
      },
      "Resolve incident",
    );
  }
  function planRollback(incident) {
    openForm(
      "Prepare rollback plan",
      "Create pending compensation records for this incident. No external tools will be executed and no data will be restored automatically.",
      [],
      async () => {
        await api("breaker", "api/v1/incidents/" + incident.id + "/rollback", {});
        return api("breaker", "api/v1/incidents/" + incident.id + "/rollbacks");
      },
      "Prepare plan",
    );
  }
  function resolveAlert(alert) {
    openForm(
      "Resolve reliability alert",
      "Resolve this alert. An ongoing breach may generate another alert; its enforcement policy remains active.",
      [],
      async () => {
        await api("slo", "api/v1/alerts/" + alert.id + "/resolve", {});
      },
      "Resolve alert",
    );
  }
  const failureModes = {
    llm: ["timeout", "model_downgrade", "hallucination", "refusal"],
    tool: ["timeout", "crash", "bad_output", "wrong_data"],
    rag: ["no_results", "bad_data", "corrupted_context", "slow_response"],
    mcp: ["server_down", "timeout", "bad_capabilities", "auth_failure"],
  };
  function createScenario() {
    openForm(
      "Create a scenario",
      "Define a simulated fault. This does not attach to or perturb a live agent.",
      [
        {
          name: "name",
          label: "Scenario name",
          required: true,
          placeholder: "tool-crash-check",
          full: true,
        },
        { name: "target_type", label: "Target", options: Object.keys(failureModes), value: "tool" },
        { name: "failure_mode", label: "Failure mode", options: failureModes.tool },
        {
          name: "expected_behavior",
          label: "Expected response",
          options: [
            "graceful_degradation",
            "fail_fast",
            "retry_success",
            "fallback_used",
            "error_handled",
          ],
          full: true,
        },
        {
          name: "config",
          label: "Configuration",
          type: "textarea",
          value: '{"params": {"delay_seconds": 0.1}}',
          full: true,
        },
        { name: "description", label: "Description", placeholder: "Optional", full: true },
      ],
      async (v) => {
        await api("chaos", "api/v1/scenarios", {
          ...v,
          config: json(v.config, "Configuration"),
          agent_should_survive: true,
          enabled: true,
        });
      },
      "Create scenario",
    );
    $("form-target_type").addEventListener("change", (e) => {
      $("form-failure_mode").replaceChildren(
        ...failureModes[e.target.value].map((mode) => el("option", { value: mode, text: mode })),
      );
    });
  }
  function runExperiment(scenario, batch = false) {
    if (!requireAgents()) return;
    if (!list("scenarios").length) {
      toast("Create or seed a scenario first.", true);
      return;
    }
    const fields = [
      {
        name: "agent_id",
        label: "Agent identity",
        options: agentOptions(),
        required: true,
        full: true,
      },
    ];
    if (batch)
      fields.push({
        name: "scenarios",
        label: "Scenarios (select multiple)",
        options: list("scenarios").map((s) => [s.id, s.name]),
        multiple: true,
        required: true,
        full: true,
      });
    else
      fields.push({
        name: "scenario_id",
        label: "Scenario",
        options: list("scenarios").map((s) => [s.id, s.name]),
        value: scenario?.id,
        required: true,
        full: true,
      });
    if (!batch)
      fields.push({
        name: "config",
        label: "Configuration override",
        type: "textarea",
        value: '{"params": {"delay_seconds": 0.1}}',
        full: true,
        help: "Timeout scenarios otherwise may run for 25–120 seconds.",
      });
    openForm(
      batch ? "Run scenario batch" : "Run fault simulation",
      "Runs real simulation requests and records results. No live agent response is observed; resilience remains unscored. Long scenarios can take up to 150 seconds per request.",
      fields,
      async (v) => {
        const body = batch
          ? { agent_id: v.agent_id, scenarios: v.scenarios }
          : {
              agent_id: v.agent_id,
              scenario_id: v.scenario_id,
              config_override: json(v.config, "Override"),
            };
        return api("chaos", "api/v1/experiments" + (batch ? "/batch" : ""), body);
      },
      "Run simulation",
    );
  }
  function seedScenarios() {
    openForm(
      "Seed built-in scenarios",
      "Create any missing built-in fault scenarios across LLM, tool, RAG, and MCP targets.",
      [],
      async () => {
        await api("chaos", "api/v1/scenarios/seed", {});
      },
      "Seed scenarios",
    );
  }
  function proposals(refine = false) {
    if (!requireAgents()) return;
    openForm(
      refine ? "Refine scenario suggestions" : "Suggest scenarios",
      "Uses the chaos service’s configured OpenAI credentials and may incur provider charges. The service currently returns suggestions, not validated or automatically applied scenarios.",
      [
        { name: "agent_id", label: "Agent", options: agentOptions(), required: true, full: true },
        { name: "model", label: "Model", value: "gpt-4o", required: true, full: true },
      ],
      async (v) => {
        const result = await api("chaos", "api/v1/scenarios/" + (refine ? "refine" : "propose"), v);
        if (!result.proposals?.length)
          throw new Error("No suggestions returned. Check provider credentials and service logs.");
        return result;
      },
      refine ? "Refine suggestions" : "Generate suggestions",
    );
  }
  function createReport() {
    openForm(
      "Create experiment report",
      "Summarize recorded experiments. Unobserved simulations are listed separately and do not count as passed tests.",
      [
        {
          name: "name",
          label: "Report name",
          required: true,
          value: "Resilience review",
          full: true,
        },
        { name: "description", label: "Description", placeholder: "Optional", full: true },
      ],
      async (v) => api("chaos", "api/v1/reports?" + new URLSearchParams(v), {}),
      "Create report",
    );
  }
  async function download(service, path, filename) {
    try {
      const value = await api(service, path);
      const blob = new Blob([typeof value === "string" ? value : JSON.stringify(value, null, 2)], {
        type: filename.endsWith(".json") ? "application/json" : "text/plain",
      });
      const url = URL.createObjectURL(blob);
      const anchor = el("a", { href: url, download: filename });
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      toast(error.message, true);
    }
  }
  function exportEvents() {
    const blob = new Blob([JSON.stringify(state.events, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = el("a", { href: url, download: "agentops-events.json" });
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function overview() {
    const calls = list("calls"),
      blocked = calls.filter((c) => c.blocked),
      statuses = list("status"),
      healthy = statuses.filter((s) => !s.is_breaching && s.data_available);
    const allHealthy = state.health?.status === "ok" && !state.errors.length;
    const hero = el("section", { class: "hero" }, [
      el("div", {}, [
        el("p", { class: "eyebrow", text: "YOUR OPERATIONS, IN FOCUS" }),
        el("h2", { text: "Your agents. Under control." }),
        el("p", { text: "Monitor execution, enforce boundaries, and respond with confidence." }),
      ]),
      el("div", { class: "hero-status" }, [
        el("strong", {}, [
          el("span", { class: "dot" + (allHealthy ? "" : " pending") }),
          el("span", {
            text: allHealthy ? "All systems operational" : "Some systems need attention",
          }),
        ]),
        el("small", { text: "Live data from your workspace" }),
      ]),
    ]);
    const metrics = el("div", { class: "metrics-grid" }, [
      metric(
        "Registered agents",
        state.data.agents ? list("agents").length : "—",
        "Identities connected to this tenant",
        "◇",
      ),
      metric(
        "Tool calls",
        state.data.calls ? calls.length : "—",
        "Latest 100 recorded decisions",
        "↗",
      ),
      metric(
        "Open incidents",
        state.data.incidents ? list("incidents").length : "—",
        "Unresolved safety events",
        "⊙",
      ),
      metric(
        "Objectives meeting target",
        state.data.status ? healthy.length + " / " + statuses.length : "—",
        "Objectives with observed data",
        "⌁",
      ),
    ]);
    const chartBody = el("div", { class: "panel-body" });
    chartBody.append(
      el("div", { class: "chart-summary" }, [
        el("div", {}, [
          el("strong", { text: number(calls.length - blocked.length) }),
          el("small", { text: "allowed calls · latest sample" }),
        ]),
        el("div", {}, [
          el("strong", { text: number(blocked.length) }),
          el("small", { text: "blocked calls · latest sample" }),
        ]),
      ]),
    );
    const bins = Array.from({ length: 12 }, () => ({ allowed: 0, blocked: 0 })),
      start = Date.now() - 3600000;
    for (const call of calls) {
      const at = new Date(call.timestamp).getTime();
      const n = Math.floor((at - start) / 300000);
      if (n >= 0 && n < 12) bins[n][call.blocked ? "blocked" : "allowed"]++;
    }
    const max = Math.max(1, ...bins.map((b) => b.allowed + b.blocked));
    if (bins.some((b) => b.allowed + b.blocked)) {
      const chart = el("div", {
        class: "chart",
        role: "img",
        "aria-label": "Recorded tool decisions over the last hour, in five minute intervals",
      });
      for (const bin of bins) {
        const stack = el("div", {
          class: "bar-stack",
          title: bin.allowed + " allowed, " + bin.blocked + " blocked",
        });
        const a = el("div", { class: "bar-allowed" }),
          b = el("div", { class: "bar-blocked" });
        a.style.height = (bin.allowed / max) * 145 + "px";
        b.style.height = (bin.blocked / max) * 145 + "px";
        stack.append(b, a);
        chart.append(el("div", { class: "chart-bin" }, [stack]));
      }
      chartBody.append(
        chart,
        el("div", { class: "chart-axis" }, [
          el("span", { text: "60 minutes ago" }),
          el("span", { text: "30 minutes ago" }),
          el("span", { text: "Now" }),
        ]),
      );
    } else
      chartBody.append(
        empty("No recent execution", "Tool calls from the last hour will appear here."),
      );
    const legend = el("div", { class: "legend" }, [
      el("span", {}, [el("i"), document.createTextNode("Allowed")]),
      el("span", {}, [el("i", { class: "blocked" }), document.createTextNode("Blocked")]),
    ]);
    const incidents = list("incidents").slice(0, 4);
    const incidentBody = el(
      "div",
      {},
      incidents.length
        ? incidents.map((i) =>
            el("div", { class: "incident-mini" }, [
              el("span", { class: "incident-icon", text: "!" }),
              el("div", {}, [
                el("strong", { text: i.category.replaceAll("_", " ") }),
                el("p", { text: agentName(i.agent_id) }),
                btn("Inspect", () => detail("Incident", i), "text", true),
              ]),
              el("time", { text: ago(i.created_at) }),
            ]),
          )
        : [empty("No open incidents", "New safety incidents will appear here.")],
    );
    const activity = el(
      "div",
      {},
      state.events.slice(0, 5).map((e) =>
        el("div", { class: "activity-item" }, [
          el("span", { class: "activity-icon", text: "↗" }),
          el("div", {}, [
            el("strong", {
              text: e.event_type.replace(/^agentops\./, "").replaceAll(".", " · "),
            }),
            el("p", { text: agentName(e.payload?.agent_id || e.agent_id) }),
          ]),
          el("time", { text: ago(e.timestamp) }),
        ]),
      ),
    );
    if (!state.events.length)
      activity.append(
        empty("Waiting for activity", "Live events will appear as your agents operate."),
      );
    const serviceNames = {
      "circuit-breaker": "Circuit Breaker",
      "chaos-toolkit": "Chaos Toolkit",
      "slo-platform": "SLO Platform",
      gateway: "Gateway",
      nats: "NATS broker",
    };
    const services = el(
      "div",
      { class: "service-grid" },
      Object.entries(serviceNames).map(([key, name]) => {
        const value = state.health?.services?.[key];
        return el("div", { class: "service-tile" }, [
          el("span", { class: "dot" + (value?.status === "ok" ? "" : " error") }),
          el("div", {}, [
            el("strong", { text: name }),
            el("small", {
              text: value?.status === "ok" ? "Operational" : value ? "Unavailable" : "Checking",
            }),
          ]),
        ]);
      }),
    );
    const topAgents = list("agents")
      .slice(0, 4)
      .map((a) => [
        identity(a.name, short(a.id)),
        badge(a.environment),
        el("span", { text: a.framework || "Custom" }),
        btn("Inspect", () => inspectAgent(a), "ghost", true),
      ]);
    return [
      heading("Overview", "A clear view of your agent operations.", [
        btn("Check a call", () => checkCall(), "ghost"),
        btn("+ Register agent", createAgent, "primary"),
      ]),
      hero,
      metrics,
      el("div", { class: "two-col" }, [
        panel("Execution activity", "Recorded decisions · last 60 minutes", chartBody, legend),
        panel(
          "Open incidents",
          "Events that need your attention",
          incidentBody,
          btn("View all ↗", () => navigate("incidents"), "text", true),
        ),
      ]),
      el("p", { class: "section-label", text: "SERVICE HEALTH" }),
      services,
      el("div", { class: "two-col" }, [
        panel(
          "Your agents",
          "Registered identities in this workspace",
          topAgents.length
            ? el("div", { class: "table-wrap" }, [
                el("table", {}, [
                  el("thead", {}, [
                    el(
                      "tr",
                      {},
                      ["Agent", "Environment", "Framework", ""].map((t) => el("th", { text: t })),
                    ),
                  ]),
                  el(
                    "tbody",
                    {},
                    topAgents.map((row) =>
                      el(
                        "tr",
                        {},
                        row.map((c) => el("td", {}, [c])),
                      ),
                    ),
                  ),
                ]),
              ])
            : empty(
                "Your first agent starts here",
                "Register an identity to scope policies and reliability objectives.",
                btn("Register agent", createAgent, "primary"),
              ),
          btn("View all ↗", () => navigate("agents"), "text", true),
        ),
        panel(
          "Recent activity",
          "Live events across the workspace",
          activity,
          btn("View feed ↗", () => navigate("events"), "text", true),
        ),
      ]),
    ];
  }
  function agents() {
    const rows = list("agents")
      .filter(matches)
      .map((a) => {
        const scoped = list("policies").filter((p) => p.enabled && p.conditions?.agent_id === a.id);
        return [
          identity(a.name, a.id),
          badge(a.environment),
          el("span", { text: a.framework || "Custom" }),
          el("span", { text: scoped.length + " scoped policies" }),
          el("span", { text: date(a.created_at) }),
          actions([
            btn("Inspect", () => inspectAgent(a), "ghost", true),
            btn("Kill", () => killAgent(a), "danger", true),
          ]),
        ];
      });
    const graph = state.data.graph;
    return [
      heading("Agents", "Register identities, inspect decisions, and control execution.", [
        btn("Check a call", () => checkCall()),
        btn("+ Register agent", createAgent, "primary"),
      ]),
      table(
        ["Agent", "Environment", "Framework", "Protection", "Registered", "Actions"],
        rows,
        "No agents registered",
        "Register an agent to get started.",
        searchToolbar("Search agents…"),
      ),
      el("div", { class: "two-col" }, [
        panel(
          "Execution graph",
          "Observed agent-to-tool edges",
          el("div", { class: "panel-body" }, [
            el("div", { class: "metrics-grid" }, [
              metric("Agents observed", graph?.agents ?? "—", "Graph identities"),
              metric("Tool edges", graph?.tool_edges ?? "—", "Agent-to-tool relationships"),
            ]),
            el("p", {
              class: "subtle",
              text: "Graph observations are tenant-isolated. Detection quality is not benchmarked.",
            }),
          ]),
        ),
        panel(
          "Graph anomalies",
          "Structural signals requiring investigation",
          el(
            "div",
            { class: "panel-body" },
            list("anomalies").length
              ? list("anomalies").map((a) =>
                  btn(a.agent + " → " + a.tool, () => detail("Graph anomaly", a), "ghost"),
                )
              : [
                  empty(
                    "No anomalies reported",
                    "The graph detector has no current observations above its threshold.",
                  ),
                ],
          ),
        ),
      ]),
    ];
  }
  function executionLog() {
    const rows = list("calls")
      .filter((c) => matches({ ...c, agent_name: agentName(c.agent_id) }))
      .filter(
        (c) => state.filter === "all" || (state.filter === "blocked" ? c.blocked : !c.blocked),
      )
      .map((c) => [
        el("div", {}, [
          el("strong", { text: c.tool_name }),
          el("small", { text: agentName(c.agent_id) }),
        ]),
        badge(c.decision || "allow", c.blocked ? "red" : "green"),
        el("span", { class: "mono", text: c.risk_score == null ? "—" : percent(c.risk_score) }),
        el("span", {
          class: "mono",
          text: c.anomaly_score == null ? "—" : percent(c.anomaly_score),
        }),
        el("span", { class: "mono", text: number(c.token_count || 0) + " tokens" }),
        el("span", { text: date(c.timestamp) }),
        btn("Inspect", () => detail("Tool call · " + c.tool_name, c), "ghost", true),
      ]);
    return [
      heading(
        "Execution log",
        "Inspect the latest 100 recorded tool decisions, including inputs and reasons.",
        [btn("Check a call", () => checkCall(), "primary")],
      ),
      table(
        ["Tool / agent", "Decision", "Risk", "Anomaly", "Usage", "Time", ""],
        rows,
        "No tool calls recorded",
        "Evaluate a call or connect an agent through the SDK.",
        searchToolbar("Search tools, agents, inputs…", [
          ["all", "All decisions"],
          ["allowed", "Allowed calls"],
          ["blocked", "Blocked calls"],
        ]),
      ),
    ];
  }
  function policies() {
    const rows = list("policies")
      .filter(matches)
      .filter((p) => state.filter === "all" || p.policy_type === state.filter)
      .map((p) => [
        el("div", {}, [
          el("strong", { text: p.name }),
          el("small", { text: p.description || p.id }),
        ]),
        badge(p.policy_type, "violet"),
        el("span", {
          text: p.conditions?.agent_id ? agentName(p.conditions.agent_id) : "Tenant-wide",
        }),
        el("span", { class: "mono", text: p.priority }),
        badge(p.action, p.action === "kill" ? "red" : p.action === "allow" ? "green" : "amber"),
        actions([
          btn("Details", () => detail("Policy · " + p.name, p), "ghost", true),
          btn("Delete", () => deletePolicy(p), "danger", true),
        ]),
      ]);
    return [
      heading(
        "Policies",
        "Explicit boundaries for every tool call. Highest priority matches first.",
        [btn("Check a call", () => checkCall()), btn("+ Create policy", createPolicy, "primary")],
      ),
      notice(
        "Automatic lockdown policies are agent-scoped. Removing one while its SLO is still breaching can cause it to be recreated. Policy update/toggle APIs are not available; create a replacement and remove the old policy.",
      ),
      table(
        ["Policy", "Type", "Scope", "Priority", "Action", "Manage"],
        rows,
        "No policies configured",
        "Create a policy to define allowed behavior.",
        searchToolbar("Search policies…", [
          ["all", "All policy types"],
          ...Object.keys(conditions).map((k) => [k, k]),
        ]),
      ),
    ];
  }
  function incidents() {
    const rows = list("incidents")
      .filter(matches)
      .filter((i) => state.filter === "all" || i.severity === state.filter)
      .map((i) => [
        el("div", {}, [
          el("strong", { text: i.category.replaceAll("_", " ") }),
          el("small", { text: i.message }),
        ]),
        badge(i.severity, i.severity === "critical" ? "red" : "amber"),
        el("span", { text: agentName(i.agent_id) }),
        el("span", { text: date(i.created_at) }),
        actions([
          btn("Inspect", () => detail("Incident details", i), "ghost", true),
          btn("Resolve", () => resolveIncident(i), "ghost", true),
          btn("Plan rollback", () => planRollback(i), "ghost", true),
        ]),
      ]);
    return [
      heading("Incidents", "Investigate safety decisions and manage incident response."),
      notice(
        "Rollback prepares pending compensation records. It does not execute inverse tools, restore data, or issue refunds. Resolving an incident does not release enforcement.",
      ),
      table(
        ["Incident", "Severity", "Agent", "Detected", "Actions"],
        rows,
        "No open incidents",
        "Unresolved incidents from blocked calls will appear here.",
        searchToolbar("Search incidents…", [
          ["all", "All severities"],
          ["critical", "Critical"],
          ["warning", "Warning"],
          ["info", "Info"],
        ]),
      ),
    ];
  }
  function reliability() {
    const statusMap = new Map(list("status").map((s) => [s.slo_id, s]));
    const objectives = list("slos")
      .filter(matches)
      .map((s) => {
        const st = statusMap.get(s.id),
          sli = list("slis").find((i) => i.id === s.sli_id);
        const available = st?.data_available;
        const format = sli?.metric_type === "ratio" ? percent : number;
        const budget =
          available && sli?.metric_type === "ratio"
            ? Math.max(
                0,
                Math.min(
                  1,
                  st.budget_remaining / Math.max(1e-9, st.budget_consumed + st.budget_remaining),
                ),
              )
            : null;
        const bar = el("div", {}, [
          el("span", { class: "mono", text: budget !== null ? percent(budget) : "—" }),
        ]);
        if (budget !== null) {
          const span = el("span");
          span.style.width = budget * 100 + "%";
          bar.append(
            el(
              "div",
              { class: "progress" + (budget < 0.2 ? " error" : budget < 0.5 ? " warn" : "") },
              [span],
            ),
          );
        }
        return [
          el("div", {}, [
            el("strong", { text: s.name }),
            el("small", { text: s.agent_id ? agentName(s.agent_id) : "Tenant-wide" }),
          ]),
          el("span", { text: sli?.name || short(s.sli_id) }),
          el("span", {
            class: "mono",
            text:
              (s.comparator === "gt" ? "≥ " : s.comparator === "lt" ? "≤ " : "= ") +
              format(s.target),
          }),
          el("span", { class: "mono", text: available ? format(st.current_value) : "No data" }),
          bar,
          badge(
            !st
              ? "Unavailable"
              : !available
                ? "No observations"
                : st.is_breaching
                  ? "Breaching"
                  : "Meeting target",
            !available ? "" : st.is_breaching ? "red" : "green",
          ),
          btn(
            "Inspect",
            () => detail("Objective · " + s.name, { objective: s, evaluation: st }),
            "ghost",
            true,
          ),
        ];
      });
    const alerts = list("alerts")
      .filter((a) => !a.resolved_at)
      .map((a) => [
        el("div", {}, [el("strong", { text: a.message }), el("small", { text: a.slo_id })]),
        badge(a.severity, a.severity === "critical" ? "red" : "amber"),
        el("span", { class: "mono", text: number(a.burn_rate) + "×" }),
        el("span", { text: date(a.fired_at) }),
        btn("Resolve", () => resolveAlert(a), "ghost", true),
      ]);
    return [
      heading("Reliability", "Objectives, rolling error budgets, and breach alerts.", [
        btn("Import traces", importTraces),
        btn("+ Indicator", createSLI),
        btn("+ Objective", createSLO, "primary"),
      ]),
      notice(
        "Only agent-scoped SLO breaches can create targeted lockdowns. Empty windows are not treated as failures. Rolling ratio budgets are supported; threshold metrics and compliance reports require careful interpretation.",
      ),
      table(
        ["Objective / scope", "Indicator", "Target", "Current", "Budget remaining", "Status", ""],
        objectives,
        "No objectives configured",
        "Create an indicator, then an objective.",
        searchToolbar("Search objectives…"),
      ),
      panel(
        "Open reliability alerts",
        "Burn-rate multipliers reflect observed / allowed error rates",
        alerts.length
          ? table(["Alert", "Severity", "Burn", "Fired", "Action"], alerts)
          : empty(
              "No open alerts",
              "Reliability alerts will appear when configured thresholds are crossed.",
            ),
      ),
      panel(
        "Available indicators",
        "Metric names determine how telemetry is derived",
        el("div", { class: "panel-body" }, [
          el(
            "div",
            { class: "pill-list" },
            list("slis").map((s) => btn(s.name, () => detail("Indicator", s), "ghost", true)),
          ),
          list("slis").length ? null : el("p", { class: "subtle", text: "No indicators yet." }),
        ]),
      ),
    ];
  }
  function chaos() {
    const summary = state.data.resilience;
    const tabs = el(
      "div",
      { class: "tabs" },
      [
        ["scenarios", "Scenarios"],
        ["experiments", "Experiments"],
        ["reports", "Reports"],
      ].map(([id, title]) =>
        el("button", {
          class: "tab" + (state.tab === id ? " active" : ""),
          text: title,
          onclick: () => {
            state.tab = id;
            state.search = "";
            render();
          },
        }),
      ),
    );
    let content;
    if (state.tab === "scenarios") {
      const rows = list("scenarios")
        .filter(matches)
        .map((s) => [
          el("div", {}, [
            el("strong", { text: s.name }),
            el("small", { text: s.description || s.id }),
          ]),
          badge(s.target_type, "violet"),
          el("span", { text: s.failure_mode }),
          el("span", { text: s.expected_behavior.replaceAll("_", " ") }),
          actions([
            btn("Inspect", () => detail("Scenario", s), "ghost", true),
            btn("Run", () => runExperiment(s), "primary", true),
          ]),
        ]);
      content = table(
        ["Scenario", "Target", "Fault", "Expected behavior", "Actions"],
        rows,
        "No scenarios available",
        "Seed built-in scenarios or create a custom one.",
        searchToolbar("Search scenarios…"),
      );
    } else if (state.tab === "experiments") {
      const rows = list("experiments")
        .filter(matches)
        .map((e) => [
          el("div", {}, [
            el("strong", { text: e.scenario_name }),
            el("small", { text: short(e.id) + " · " + agentName(e.agent_id) }),
          ]),
          badge(e.status, e.status === "failed" ? "red" : "green"),
          badge(
            e.resilience_score == null
              ? "Unobserved"
              : e.agent_survived
                ? "Observed survival"
                : "Observed failure",
            e.resilience_score == null ? "" : e.agent_survived ? "green" : "red",
          ),
          el("span", {
            class: "mono",
            text: e.resilience_score == null ? "Unscored" : percent(e.resilience_score),
          }),
          el("span", { text: date(e.created_at) }),
          btn("Inspect", () => detail("Experiment", e), "ghost", true),
        ]);
      content = table(
        ["Experiment", "Simulation", "Agent outcome", "Score", "Started", ""],
        rows,
        "No experiments recorded",
        "Run a simulation from the scenarios tab.",
        searchToolbar("Search experiments…"),
      );
    } else {
      const rows = list("reports")
        .filter(matches)
        .map((r) => [
          el("div", {}, [
            el("strong", { text: r.name }),
            el("small", { text: r.description || short(r.id) }),
          ]),
          el("span", { text: date(r.created_at) }),
          el("span", { text: (r.summary?.unobserved || 0) + " unobserved" }),
          actions([
            btn("Inspect", () => detail("Experiment report", r), "ghost", true),
            btn(
              "JUnit",
              () => download("chaos", "api/v1/reports/" + r.id + "/junit", r.id + ".xml"),
              "ghost",
              true,
            ),
            btn(
              "Summary",
              () => download("chaos", "api/v1/reports/" + r.id + "/github-summary", r.id + ".md"),
              "ghost",
              true,
            ),
          ]),
        ]);
      content = table(
        ["Report", "Created", "Coverage", "Export"],
        rows,
        "No reports created",
        "Create a report to summarize recorded experiments.",
        searchToolbar("Search reports…"),
      );
    }
    return [
      heading("Chaos lab", "Explore failure modes with controlled fault simulations.", [
        btn("Seed scenarios", seedScenarios),
        btn("+ Scenario", createScenario, "primary"),
      ]),
      notice(
        "Simulation mode · Faults are generated locally; no live agent is perturbed. Successful injection does not prove resilience. Unobserved agent outcomes remain unscored. Timeout scenarios may take up to 120 seconds.",
      ),
      el("div", { class: "metrics-grid" }, [
        metric("Experiments", summary?.total_experiments ?? "—", "Recorded simulation runs", "⚗"),
        metric("Observed passes", summary?.passed ?? "—", "Requires an observed outcome", "↗"),
        metric(
          "Observed failures",
          summary?.failed ?? "—",
          "Measured results below threshold",
          "⊙",
        ),
        metric("Unobserved", summary?.unobserved ?? "—", "Not included in pass rate", "◇"),
      ]),
      el("div", { class: "actions", style: "margin-bottom:18px" }, [
        btn("Run batch", () => runExperiment(null, true)),
        btn("Suggest with LLM", () => proposals()),
        btn("Refine suggestions", () => proposals(true)),
        btn("Create report", createReport),
      ]),
      tabs,
      content,
    ];
  }
  function events() {
    let data = state.events.filter(matches);
    if (state.filter !== "all") data = data.filter((e) => e.event_type.includes(state.filter));
    return [
      heading("Live events", "Tenant-scoped activity from the NATS event stream.", [
        btn("Export JSON", exportEvents),
      ]),
      el("section", { class: "panel" }, [
        searchToolbar("Search event type, agent, payload…", [
          ["all", "All event types"],
          ["cb.intercept", "Tool decisions"],
          ["cb.incident", "Incidents"],
          ["cb.kill", "Kill switches"],
          ["slo.", "Reliability"],
          ["chaos.", "Chaos experiments"],
        ]),
        data.length
          ? el(
              "div",
              { class: "timeline" },
              data.slice(0, 200).map((e) => eventRow(e, (event) => detail("Event details", event))),
            )
          : empty("No matching events", "Adjust the filter or wait for new workspace activity."),
        el("div", { class: "table-footer" }, [
          el("span", {
            text:
              Math.min(data.length, 200) +
              " visible · " +
              state.events.length +
              " buffered in this page",
          }),
          badge(state.live ? "Live stream" : "Polling fallback", state.live ? "green" : "amber"),
        ]),
      ]),
    ];
  }
  function settings() {
    const tenant = state.data.tenant || {};
    return [
      heading("Workspace & reports", "Tenant information, evidence exports, and operating limits."),
      panel(
        "Workspace identity",
        "Authentication is handled by the dashboard server",
        el("div", { class: "panel-body" }, [
          el(
            "div",
            { class: "detail-grid" },
            Object.entries({
              Name: tenant.name || "Unavailable",
              Slug: tenant.slug || "—",
              "Tenant ID": tenant.id || "—",
              Created: date(tenant.created_at),
            }).map(([key, value]) =>
              el("div", {}, [
                el("small", { text: key }),
                el("strong", { class: key === "Tenant ID" ? "mono" : "", text: value }),
              ]),
            ),
          ),
          el("p", {
            class: "subtle",
            text: "The API key is never embedded in this page. Key rotation must be coordinated with the dashboard runtime configuration; it is intentionally unavailable here.",
          }),
        ]),
      ),
      el("div", { class: "report-grid" }, [
        el("section", { class: "report-card" }, [
          badge("CONFIGURATION COVERAGE", "amber"),
          el("h3", { text: "OWASP control mapping" }),
          el("p", {
            text: "Reports which SLO indicators are configured. This is not a control effectiveness test or certification.",
          }),
          btn("View report", async () => {
            try {
              detail("OWASP configuration mapping", await api("slo", "api/v1/compliance/owasp"));
            } catch (e) {
              toast(e.message, true);
            }
          }),
          btn(
            "Download",
            () => download("slo", "api/v1/compliance/owasp", "owasp-configuration.json"),
            "ghost",
          ),
        ]),
        el("section", { class: "report-card" }, [
          badge("EVIDENCE SCAFFOLD", "amber"),
          el("h3", { text: "EU AI Act evidence" }),
          el("p", {
            text: "Inspect the current traceability scaffold. It does not establish legal compliance.",
          }),
          btn("View scaffold", async () => {
            try {
              detail(
                "EU AI Act evidence scaffold",
                await api("slo", "api/v1/compliance/eu-ai-act"),
              );
            } catch (e) {
              toast(e.message, true);
            }
          }),
          btn(
            "Download",
            () => download("slo", "api/v1/compliance/eu-ai-act", "eu-ai-act-scaffold.json"),
            "ghost",
          ),
        ]),
      ]),
      el("p", { class: "section-label", text: "SUPPORTED WORKSPACE OPERATIONS" }),
      notice(
        "Python enforcement is the supported default. Native C evaluation is experimental. Rollback records require external execution and confirmation. Chaos simulations do not measure unobserved agent behavior. Predictions are estimates, and event history in the gateway is bounded and in memory.",
      ),
    ];
  }
  const pages = {
    overview,
    agents,
    calls: executionLog,
    policies,
    incidents,
    slos: reliability,
    chaos,
    events,
    settings,
  };
  function render() {
    const active = document.activeElement,
      id = active?.id,
      start = active?.selectionStart;
    const parts = pages[state.page]();
    $("main").replaceChildren(...parts.filter(Boolean));
    if (id && $(id)) {
      try {
        $(id).focus({ preventScroll: true });
        if (start !== null && start !== undefined) $(id).setSelectionRange(start, start);
      } catch {}
    }
  }
  function navigate(page) {
    location.hash = page;
  }
  function route() {
    const page = location.hash.slice(1) || "overview";
    state.page = names[page] ? page : "overview";
    state.search = "";
    state.filter = "all";
    $("breadcrumb").textContent = names[state.page];
    document.title = names[state.page] + " · AgentOps";
    document.querySelectorAll("[data-page]").forEach((a) => {
      const selected = a.dataset.page === state.page;
      a.classList.toggle("active", selected);
      if (selected) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    $("sidebar").classList.remove("open");
    $("menu-toggle").setAttribute("aria-expanded", "false");
    if (state.updated) render();
  }
  function connect() {
    const ws = new WebSocket(
      (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws",
    );
    ws.onopen = () => {
      state.live = true;
      $("connection-status").replaceChildren(
        el("span", { class: "dot" }),
        document.createTextNode("Live stream"),
      );
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "pong") return;
        addEvents([data]);
        if (
          (state.page === "overview" || state.page === "events") &&
          !$("main").contains(document.activeElement)
        )
          render();
      } catch {}
    };
    ws.onclose = () => {
      state.live = false;
      $("connection-status").replaceChildren(
        el("span", { class: "dot pending" }),
        document.createTextNode("Polling fallback"),
      );
      setTimeout(connect, 5000);
    };
    ws.onerror = () => ws.close();
  }
  $("refresh").addEventListener("click", refresh);
  $("modal-close").addEventListener("click", closeModal);
  $("modal").addEventListener("cancel", (event) => {
    if ($("modal").dataset.busy) event.preventDefault();
  });
  $("menu-toggle").addEventListener("click", () => {
    const open = $("sidebar").classList.toggle("open");
    $("menu-toggle").setAttribute("aria-expanded", String(open));
  });
  window.addEventListener("hashchange", route);
  let shortcutUntil = 0;
  document.addEventListener("keydown", (event) => {
    if (
      !$("modal").open &&
      !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
    ) {
      if (event.key.toLowerCase() === "g") shortcutUntil = Date.now() + 1200;
      else if (event.key.toLowerCase() === "o" && Date.now() < shortcutUntil) {
        navigate("overview");
        shortcutUntil = 0;
      }
    }
    if (event.key === "Escape") {
      $("sidebar").classList.remove("open");
      $("menu-toggle").setAttribute("aria-expanded", "false");
    }
  });
  route();
  refresh().then(connect);
  setInterval(refresh, 20000);
})();
