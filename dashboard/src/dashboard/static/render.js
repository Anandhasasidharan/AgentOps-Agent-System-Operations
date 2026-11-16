(function (root) {
  "use strict";
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined) continue;
      if (key === "text") node.textContent = String(value);
      else if (key === "class") node.className = value;
      else if (key.startsWith("on") && typeof value === "function")
        node.addEventListener(key.slice(2), value);
      else if (["checked", "disabled", "selected", "required", "multiple", "hidden"].includes(key))
        node[key] = value;
      else node.setAttribute(key, String(value));
    }
    for (const child of [].concat(children))
      if (child !== null && child !== undefined)
        node.append(typeof child === "string" ? document.createTextNode(child) : child);
    return node;
  }
  function badge(text, tone = "") {
    return el("span", { class: "badge " + tone, text });
  }
  function eventRow(event, onClick) {
    const payload = event.payload || {};
    const kind = String(event.event_type || "event").replace(/^agentops\./, "");
    const tone = /kill|block|critical/.test(kind + (payload.verdict || ""))
      ? "red"
      : /breach|incident/.test(kind)
        ? "amber"
        : /chaos/.test(kind)
          ? "violet"
          : "green";
    return el(
      "button",
      {
        class: "event-row",
        type: "button",
        onclick: () => onClick && onClick(event),
        "aria-label": "Inspect " + kind,
      },
      [
        el("time", {
          text: event.timestamp
            ? new Date(event.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })
            : "—",
        }),
        badge(kind, tone),
        el("span", {
          class: "event-agent",
          text: payload.agent_id || event.agent_id || "Workspace",
        }),
        el("span", { class: "event-payload", text: JSON.stringify(payload) }),
      ],
    );
  }
  root.AgentOpsRender = { el, badge, eventRow };
})(globalThis);
