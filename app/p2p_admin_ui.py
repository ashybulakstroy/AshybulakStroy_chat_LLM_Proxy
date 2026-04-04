P2P_ADMIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>P2P Debug Admin</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #1f2a30;
      --muted: #6f7a80;
      --line: #d9d1c3;
      --accent: #1d6f63;
      --accent-soft: #dcefe9;
      --warn: #8f4d20;
      --ok: #216b45;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top right, #e4efe8, transparent 26%),
        linear-gradient(180deg, #f6f3ec 0%, var(--bg) 100%);
      color: var(--ink);
    }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 28px 18px 40px; }
    .hero, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 14px 36px rgba(31, 45, 43, 0.08);
    }
    .hero { padding: 24px; margin-bottom: 18px; }
    .hero h1 {
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 52px);
      line-height: 0.95;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 900px;
      font-size: 16px;
      line-height: 1.5;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }
    .panel { padding: 18px; }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 24px;
      line-height: 1.1;
    }
    .metric {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 0;
      border-top: 1px solid var(--line);
    }
    .metric:first-of-type { border-top: 0; }
    .k {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }
    .v {
      font-weight: 700;
      text-align: right;
      font-size: 24px;
      line-height: 1.1;
    }
    .badge {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .ok { color: var(--ok); font-weight: 700; }
    .warn { color: var(--warn); font-weight: 700; }
    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    .stack {
      display: grid;
      gap: 16px;
      margin-bottom: 18px;
    }
    .row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    input, select, button {
      width: 100%;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 10px 16px;
      font: inherit;
      background: white;
      font-size: 14px;
    }
    button {
        cursor: pointer;
        background: var(--accent);
        color: white;
        border: 0;
        box-shadow: 0 14px 36px rgba(31, 45, 43, 0.08);
      }
    button.table-action {
        width: auto;
        min-width: 0;
        padding: 8px 14px;
        white-space: nowrap;
        font-size: 13px;
      }
    table {
        width: 100%;
        border-collapse: collapse;
        min-width: 760px;
      }
    .table-wrap {
        width: 100%;
        overflow-x: auto;
      }
    table.peer-table {
        min-width: 0;
        table-layout: fixed;
      }
    table.peer-table th,
    table.peer-table td {
        overflow-wrap: anywhere;
        word-break: break-word;
      }
    .mono-wrap {
        word-break: break-all;
        overflow-wrap: anywhere;
      }
    .compact-lines {
        line-height: 1.25;
      }
    th, td {
        text-align: left;
        padding: 12px 10px;
        border-top: 1px solid var(--line);
        vertical-align: top;
      font-size: 14px;
      line-height: 1.35;
    }
    th {
      color: var(--muted);
      font-weight: 600;
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      line-height: 1.45;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="toolbar">
        <div>
          <h1>P2P Debug Admin</h1>
          <p>Minimal live runtime page for node config, known peers, heartbeat and P2P session counters.</p>
        </div>
        <button id="refresh">Refresh</button>
      </div>
      <span class="badge" id="enabled-badge">Loading</span>
    </section>

    <section class="panel" style="margin-bottom: 18px;">
      <h2>Online Resource Summary</h2>
      <table>
        <thead>
            <tr>
              <th>Online Routes</th>
              <th>Routes With FREE Slots</th>
              <th>Routes Without FREE Slots</th>
              <th>Shared Slots Total</th>
              <th>Busy Slots</th>
            </tr>
          </thead>
          <tbody id="online-resource-summary-table">
            <tr><td colspan="5">No summary yet.</td></tr>
          </tbody>
        </table>
    </section>

    <section class="panel" style="margin-bottom: 18px;">
      <h2>Network Map</h2>
      <table>
        <thead>
            <tr>
              <th>Segment</th>
              <th>Count</th>
              <th>Providers</th>
              <th>Routes</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody id="network-map-table">
          <tr><td colspan="5">No network map data yet.</td></tr>
          </tbody>
        </table>
    </section>

      <section class="panel" style="margin-bottom: 18px;">
        <h2 id="known-peers-title">Known Peers (0)</h2>
        <table class="peer-table">
          <thead>
            <tr>
                <th>Mode</th>
              <th>Peer ID</th>
            <th>Name</th>
            <th>Mode</th>
            <th>Scope</th>
              <th>Run</th>
            <th>Route Status</th>
            <th>Route Type</th>
            <th>Health</th>
            <th>Capabilities</th>
              <th>Providers / Models</th>
              <th>Active</th>
              <th>Heartbeat</th>
              <th>URL</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="peer-table">
            <tr><td colspan="15">No peers discovered yet.</td></tr>
          </tbody>
        </table>
      </section>

    <section class="panel" style="margin-bottom: 18px;">
      <h2 id="routing-title">Маршрутизация (0)</h2>
      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Node</th>
            <th>Route ID</th>
            <th>Resource</th>
            <th>Slots / Min</th>
            <th>Route Status</th>
          </tr>
        </thead>
        <tbody id="routing-table">
          <tr><td colspan="6">No routing resources yet.</td></tr>
        </tbody>
      </table>
    </section>

    <section class="stack">
      <article class="panel">
        <h2>Runtime Control</h2>
        <div class="row">
          <select id="node-mode">
            <option value="peer">peer</option>
            <option value="auto">auto</option>
            <option value="master_cache">master_cache</option>
            <option value="master">master</option>
          </select>
          <select id="p2p-enabled">
            <option value="true">P2P enabled</option>
            <option value="false">P2P disabled</option>
          </select>
          <button id="save-runtime">Apply Runtime Config</button>
        </div>
      </article>

      <article class="panel">
        <h2>Peer Heartbeat Debug</h2>
        <div class="row">
          <input id="peer-id" placeholder="peer_id" />
          <input id="peer-name" placeholder="node_name" />
          <input id="peer-url" placeholder="base_url" />
          <select id="peer-mode">
            <option value="peer">peer</option>
            <option value="master">master</option>
            <option value="master_cache">master_cache</option>
            <option value="auto">auto</option>
          </select>
          <select id="peer-scope">
            <option value="private">private</option>
            <option value="public">public</option>
          </select>
          <select id="peer-status">
            <option value="online">online</option>
            <option value="degraded">degraded</option>
            <option value="paused">paused</option>
          </select>
          <input id="peer-health" type="number" min="0" max="1" step="0.1" placeholder="health_score (0..1)" />
          <input id="peer-active-sessions" type="number" min="0" placeholder="active_sessions" />
          <input id="peer-providers" placeholder="providers csv" />
          <input id="peer-models" placeholder="models csv" />
          <select id="peer-accept-remote">
            <option value="true">accept_remote_tasks=true</option>
            <option value="false">accept_remote_tasks=false</option>
          </select>
          <select id="peer-share-capacity">
            <option value="true">share_capacity=true</option>
            <option value="false">share_capacity=false</option>
          </select>
          <select id="peer-direct-provider-access">
            <option value="true">direct_provider_access=true</option>
            <option value="false">direct_provider_access=false</option>
          </select>
          <select id="peer-supports-chat">
            <option value="true">supports_chat=true</option>
            <option value="false">supports_chat=false</option>
          </select>
          <select id="peer-supports-embeddings">
            <option value="true">supports_embeddings=true</option>
            <option value="false">supports_embeddings=false</option>
          </select>
          <button id="send-heartbeat">Upsert Peer Heartbeat</button>
        </div>
      </article>

      <article class="panel">
        <h2>Session Counters Debug</h2>
        <div class="row">
          <input id="incoming-count" type="number" min="0" placeholder="active incoming" />
          <input id="outgoing-count" type="number" min="0" placeholder="active outgoing" />
          <input id="queue-count" type="number" min="0" placeholder="queued tasks" />
          <button id="save-counters">Apply Counters</button>
        </div>
      </article>

      <article class="panel">
        <h2>Dispatch Preview</h2>
        <div class="row">
          <input id="dispatch-provider" placeholder="requested provider (auto)" />
          <input id="dispatch-model" placeholder="requested model (auto)" />
          <select id="dispatch-mode">
            <option value="">use current mode</option>
            <option value="FAST">FAST</option>
            <option value="LOAD_BALANCE">LOAD_BALANCE</option>
            <option value="LOCAL_FIRST">LOCAL_FIRST</option>
            <option value="COST_EFFECTIVE">COST_EFFECTIVE</option>
          </select>
          <select id="dispatch-task-type">
            <option value="chat_completion">chat_completion</option>
            <option value="embeddings">embeddings</option>
          </select>
          <button id="run-dispatch-preview">Run Dispatch Preview</button>
        </div>
        <pre id="dispatch-preview-output">No dispatch preview yet.</pre>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>Node</h2>
        <div id="node-metrics"></div>
      </article>
      <article class="panel">
        <h2>Master</h2>
        <div id="master-metrics"></div>
      </article>
      <article class="panel">
        <h2>Limits</h2>
        <div id="limit-metrics"></div>
      </article>
      <article class="panel">
        <h2>Sessions</h2>
        <div id="session-metrics"></div>
      </article>
      <article class="panel">
        <h2>Heartbeat</h2>
        <div id="heartbeat-metrics"></div>
      </article>
    </section>

    <section class="panel">
      <h2>Raw Status</h2>
      <pre id="raw-status">Loading...</pre>
    </section>
  </div>

  <script>
    function renderMetrics(targetId, data) {
      const target = document.getElementById(targetId);
      target.innerHTML = "";
      Object.entries(data).forEach(([key, value]) => {
        const row = document.createElement("div");
        row.className = "metric";
        row.innerHTML = `<div class="k">${key}</div><div class="v">${String(value)}</div>`;
        target.appendChild(row);
      });
    }

    function renderOnlineResourceSummary(data) {
      const tbody = document.getElementById("online-resource-summary-table");
      if (!data || Object.keys(data).length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">No summary yet.</td></tr>';
        return;
      }
      tbody.innerHTML = `
          <tr>
            <td>${data.ready_routes ?? 0}</td>
            <td>${data.routes_with_slots ?? 0}</td>
            <td>${data.routes_without_free_slots ?? 0}</td>
            <td>${data.shared_slots_total ?? 0}</td>
            <td>${data.busy_slots ?? 0}</td>
          </tr>
        `;
    }

    function formatHeartbeatAge(value) {
      if (!value) {
        return "";
      }
      const timestamp = Date.parse(value);
      if (Number.isNaN(timestamp)) {
        return value;
      }
      const diffSec = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
      return `${diffSec} sec ago`;
    }

    function formatPeerKey(value) {
      const text = String(value || "");
      return text
        .replaceAll("::", "::вЂ‹")
        .replaceAll("://", "://вЂ‹")
        .replaceAll("/", "/вЂ‹");
    }

    function formatCapabilities(peer) {
      return [
        `chat=${Boolean(peer.supports_chat)}`,
        `emb=${Boolean(peer.supports_embeddings)}`,
        `remote=${Boolean(peer.accept_remote_tasks)}`,
        `direct=${Boolean(peer.direct_provider_access)}`,
      ].join("<br>");
    }

    function formatProvidersModels(peer) {
      const providers = (peer.providers || []).join(", ");
      const models = (peer.models || []).slice(0, 3).join(", ");
      return `${providers}${models ? `<br>${models}` : ""}`;
    }

    function renderPeers(peers, masters) {
      const tbody = document.getElementById("peer-table");
      const title = document.getElementById("known-peers-title");
      const peerRows = Array.isArray(peers) ? peers : [];
      const masterRows = Array.isArray(masters) ? masters : [];
      const rows = [
        ...masterRows.map((item) => ({ kind: "master", row_id: item.route_id || item.base_url || "", ...item })),
        ...peerRows.map((item) => ({ kind: "peer", row_id: item.peer_id || "", ...item })),
      ];
      if (title) {
        title.textContent = `Маршрутизация (${rows.length})`;
      }
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="15">No peers discovered yet.</td></tr>';
        return;
      }
          tbody.innerHTML = rows.map((peer) => `
            <tr${Number(peer.health_score ?? "") === 0 ? ' style="background:#fff1f2;"' : ""}>
              <td>${peer.kind || ""}</td>
              <td class="mono-wrap">${formatPeerKey(peer.peer_id || peer.route_id || "")}</td>
              <td>${peer.node_name || ""}</td>
            <td>${peer.node_mode || ""}</td>
            <td>${peer.scope || ""}</td>
            <td>${peer.runtime_status || peer.status || ""}</td>
            <td>${peer.route_status || ""}</td>
            <td>${peer.direct_provider_access ? "direct" : "link-only"}</td>
            <td>${peer.health_score ?? ""}</td>
              <td class="compact-lines">${formatCapabilities(peer)}</td>
                <td class="compact-lines">${formatProvidersModels(peer)}</td>
                <td>${peer.active_sessions ?? 0}</td>
                <td>${formatHeartbeatAge(peer.last_heartbeat_at)}</td>
                <td class="mono-wrap">${formatPeerKey(peer.base_url || "")}</td>
                <td>${(String(peer.runtime_status || peer.status || "").toLowerCase() === "error" && Number(peer.health_score ?? "") === 0)
                ? `<button class="secondary table-action" data-remove-kind="${peer.kind || ""}" data-remove-key="${peer.peer_id || peer.route_id || ""}">X</button>`
                : ""}</td>
            </tr>
          `).join("");
      }

    function renderRouting(routing) {
      const tbody = document.getElementById("routing-table");
      const title = document.getElementById("routing-title");
      const rows = Array.isArray(routing?.rows) ? routing.rows : [];
      if (title) {
        title.textContent = `Маршрутизация (${rows.length})`;
      }
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6">No routing resources yet.</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map((row) => `
        <tr>
          <td>${row.kind || ""}</td>
          <td>${row.owner_name || ""}</td>
          <td class="mono-wrap">${row.route_id || ""}</td>
          <td>${row.resource_name || ""}</td>
          <td>${row.available_slots_per_minute ?? 0}</td>
          <td>${row.route_status || ""}</td>
        </tr>
      `).join("");
    }

    function renderNetworkMap(networkMap) {
      const tbody = document.getElementById("network-map-table");
      if (!networkMap) {
        tbody.innerHTML = '<tr><td colspan="5">No network map data yet.</td></tr>';
        return;
      }
      const rows = [
        {
          segment: "Masters",
          count: networkMap.master_nodes?.count ?? 0,
          providers: networkMap.master_nodes?.direct_provider_count ?? 0,
          routes: networkMap.master_nodes?.route_count ?? 0,
          notes: `role=${networkMap.master_nodes?.role ?? ""} / direct=${Boolean(networkMap.master_nodes?.direct_provider_access)}`
        },
        {
          segment: "Peers",
          count: networkMap.peer_nodes?.count ?? 0,
          providers: networkMap.peer_nodes?.direct_provider_count ?? 0,
          routes: networkMap.peer_nodes?.route_count ?? 0,
          notes: `direct peers=${networkMap.peer_nodes?.direct_peer_count ?? 0} / link-only peers=${networkMap.peer_nodes?.link_only_peer_count ?? 0}`
        },
        {
          segment: "Direct Provider Links",
          count: networkMap.routes?.direct_provider_links ?? 0,
          providers: "-",
          routes: networkMap.routes?.online_route_count ?? 0,
          notes: "only node/provider links with direct provider access"
        },
        {
          segment: "Unique Routes",
          count: networkMap.routes?.unique_route_count ?? 0,
          providers: "-",
          routes: networkMap.routes?.unique_route_count ?? 0,
          notes: "unique routes by 12-char hash"
        },
        {
          segment: "Redundant Routes",
          count: networkMap.routes?.redundant_route_count ?? 0,
          providers: "-",
          routes: networkMap.routes?.redundant_route_count ?? 0,
          notes: "duplicates by route hash"
        }
      ];
      tbody.innerHTML = rows.map((row) => `
          <tr>
            <td>${row.segment}</td>
            <td>${row.count}</td>
            <td>${row.providers}</td>
            <td>${row.routes}</td>
            <td>${row.notes}</td>
          </tr>
        `).join("");
    }

    async function postForm(url, params) {
      const query = new URLSearchParams(params);
      const res = await fetch(`${url}?${query.toString()}`, { method: "POST" });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      return await res.json();
    }

    async function loadStatus() {
      const res = await fetch("/admin/p2p/status", { cache: "no-store" });
      const data = await res.json();
      document.getElementById("enabled-badge").textContent = data.p2p_enabled ? "P2P enabled" : "P2P disabled";
      document.getElementById("node-mode").value = data.node?.mode || "peer";
      document.getElementById("p2p-enabled").value = String(Boolean(data.p2p_enabled));
      renderMetrics("node-metrics", data.node || {});
      renderMetrics("master-metrics", data.master || {});
      renderMetrics("limit-metrics", data.limits || {});
      renderMetrics("session-metrics", data.sessions || {});
      renderMetrics("heartbeat-metrics", data.heartbeat || {});
      renderOnlineResourceSummary(data.online_resource_summary || {});
      renderNetworkMap(data.network_map || {});
      renderPeers(data.peers || [], data.masters || []);
      renderRouting(data.routing || {});
      document.getElementById("raw-status").textContent = JSON.stringify(data, null, 2);
    }

    document.getElementById("refresh").addEventListener("click", loadStatus);

    document.getElementById("save-runtime").addEventListener("click", async () => {
      await postForm("/admin/p2p/config", {
        node_mode: document.getElementById("node-mode").value,
        p2p_enabled: document.getElementById("p2p-enabled").value
      });
      await loadStatus();
    });

    document.getElementById("send-heartbeat").addEventListener("click", async () => {
      await postForm("/admin/p2p/peers/heartbeat", {
        peer_id: document.getElementById("peer-id").value,
        node_name: document.getElementById("peer-name").value,
        base_url: document.getElementById("peer-url").value,
        node_mode: document.getElementById("peer-mode").value,
        scope: document.getElementById("peer-scope").value,
        status: document.getElementById("peer-status").value,
        health_score: document.getElementById("peer-health").value || "",
        active_sessions: document.getElementById("peer-active-sessions").value || 0,
        providers: document.getElementById("peer-providers").value || "",
        models: document.getElementById("peer-models").value || "",
        accept_remote_tasks: document.getElementById("peer-accept-remote").value,
        share_capacity: document.getElementById("peer-share-capacity").value,
        direct_provider_access: document.getElementById("peer-direct-provider-access").value,
        supports_chat: document.getElementById("peer-supports-chat").value,
        supports_embeddings: document.getElementById("peer-supports-embeddings").value
      });
      await loadStatus();
    });

    document.getElementById("save-counters").addEventListener("click", async () => {
      await postForm("/admin/p2p/sessions", {
        active_incoming_sessions: document.getElementById("incoming-count").value || 0,
        active_outgoing_sessions: document.getElementById("outgoing-count").value || 0,
        queued_tasks: document.getElementById("queue-count").value || 0
      });
      await loadStatus();
    });

      document.getElementById("run-dispatch-preview").addEventListener("click", async () => {
        const payload = await postForm("/admin/p2p/dispatch/preview", {
          requested_provider: document.getElementById("dispatch-provider").value || "auto",
          requested_model: document.getElementById("dispatch-model").value || "auto",
          requested_mode: document.getElementById("dispatch-mode").value || "",
          task_type: document.getElementById("dispatch-task-type").value || "chat_completion"
        });
        document.getElementById("dispatch-preview-output").textContent = JSON.stringify(payload, null, 2);
      });

      document.getElementById("peer-table").addEventListener("click", async (event) => {
        const button = event.target.closest("[data-remove-kind][data-remove-key]");
        if (!button) {
          return;
        }
        await postForm("/admin/p2p/nodes/remove", {
          kind: button.dataset.removeKind,
          node_key: button.dataset.removeKey
        });
        await loadStatus();
      });

      loadStatus();
  </script>
</body>
</html>
"""


