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
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(circle at top right, #e4efe8, transparent 26%),
        linear-gradient(180deg, #f6f3ec 0%, var(--bg) 100%);
      color: var(--ink);
    }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 24px; }
    .hero, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(31, 42, 48, 0.06);
    }
    .hero { padding: 24px; margin-bottom: 18px; }
    .hero h1 { margin: 0 0 8px; font-size: 28px; }
    .hero p { margin: 0; color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }
    .panel { padding: 18px; }
    .panel h2 { margin: 0 0 12px; font-size: 16px; }
    .metric {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 0;
      border-top: 1px solid #eee6d8;
    }
    .metric:first-of-type { border-top: 0; }
    .k { color: var(--muted); }
    .v { font-weight: 600; text-align: right; }
    .badge {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.04em;
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
      border-radius: 10px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
      background: white;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      color: white;
      border: 0;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-top: 1px solid #eee6d8;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 600; }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
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
      <h2>Network Map</h2>
      <table>
        <thead>
          <tr>
            <th>Segment</th>
            <th>Count</th>
            <th>Providers</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody id="network-map-table">
          <tr><td colspan="4">No network map data yet.</td></tr>
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

    <section class="panel" style="margin-bottom: 18px;">
      <h2>Known Peers</h2>
      <table>
        <thead>
          <tr>
            <th>Peer ID</th>
            <th>Name</th>
            <th>Mode</th>
            <th>Scope</th>
            <th>Status</th>
            <th>Health</th>
            <th>Capabilities</th>
            <th>Providers / Models</th>
            <th>Active</th>
            <th>Heartbeat</th>
            <th>URL</th>
          </tr>
        </thead>
        <tbody id="peer-table">
          <tr><td colspan="11">No peers discovered yet.</td></tr>
        </tbody>
      </table>
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

    function renderPeers(peers) {
      const tbody = document.getElementById("peer-table");
      if (!Array.isArray(peers) || peers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11">No peers discovered yet.</td></tr>';
        return;
      }
      tbody.innerHTML = peers.map((peer) => `
        <tr>
          <td>${peer.peer_id || ""}</td>
          <td>${peer.node_name || ""}</td>
          <td>${peer.node_mode || ""}</td>
          <td>${peer.scope || ""}</td>
          <td>${peer.runtime_status || peer.status || ""}</td>
          <td>${peer.health_score ?? ""}</td>
          <td>chat=${Boolean(peer.supports_chat)} / emb=${Boolean(peer.supports_embeddings)} / remote=${Boolean(peer.accept_remote_tasks)}</td>
          <td>${(peer.providers || []).join(", ")}<br>${(peer.models || []).slice(0, 3).join(", ")}</td>
          <td>${peer.active_sessions ?? 0}</td>
          <td>${peer.last_heartbeat_at || ""}</td>
          <td>${peer.base_url || ""}</td>
        </tr>
      `).join("");
    }

    function renderNetworkMap(networkMap) {
      const tbody = document.getElementById("network-map-table");
      if (!networkMap) {
        tbody.innerHTML = '<tr><td colspan="4">No network map data yet.</td></tr>';
        return;
      }
      const rows = [
        {
          segment: "Masters",
          count: networkMap.master_nodes?.count ?? 0,
          providers: networkMap.master_nodes?.provider_count ?? 0,
          notes: `role=${networkMap.master_nodes?.role ?? ""}`
        },
        {
          segment: "Peers",
          count: networkMap.peer_nodes?.count ?? 0,
          providers: networkMap.peer_nodes?.provider_count ?? 0,
          notes: "online peer providers total"
        },
        {
          segment: "Unique Live Routes",
          count: networkMap.routes?.unique_live_routes ?? 0,
          providers: "-",
          notes: "unique alive provider routes across master + peers"
        }
      ];
      tbody.innerHTML = rows.map((row) => `
        <tr>
          <td>${row.segment}</td>
          <td>${row.count}</td>
          <td>${row.providers}</td>
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
      renderNetworkMap(data.network_map || {});
      renderPeers(data.peers || []);
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

    loadStatus();
  </script>
</body>
</html>
"""
