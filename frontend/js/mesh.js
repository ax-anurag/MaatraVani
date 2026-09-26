/* Offline Mesh page.

The transport under the hood is the in-process LocalMeshSimulation unless a
real BLE adapter is present - and the page says which one, loudly, because
the demo rule is: never let anyone mistake a simulated hop for a radio hop.

Request budget: page load does 3 GETs (status is cached, nodes, events);
each send is 1 POST + at most 1 inbox GET; everything else arrives live on
the WebSocket, which is outside the /api/* budget. */

import { el, badge, errorNote, toast } from "./ui.js";
import { fetchMeshStatus, getJSON, postForm, form } from "./api.js";

const SVG_TOPOLOGY = `
<svg viewBox="0 0 560 170" class="topology-svg" role="img"
     aria-label="Classroom mesh topology: teacher, student A, student B">
  <line x1="105" y1="78" x2="245" y2="78" class="link"></line>
  <line x1="335" y1="78" x2="475" y2="78" class="link"></line>
  <g class="mnode" data-node="teacher" transform="translate(70,78)">
    <circle r="34"></circle><text y="-42">teacher</text><title>Teacher Device</title>
  </g>
  <g class="mnode" data-node="student-a" transform="translate(280,78)">
    <circle r="34"></circle><text y="-42">student A</text><title>Student Device A</title>
  </g>
  <g class="mnode" data-node="student-b" transform="translate(490,78)">
    <circle r="34"></circle><text y="-42">student B</text><title>Student Device B</title>
  </g>
  <text x="175" y="70" class="link-label">1 hop</text>
  <text x="405" y="70" class="link-label">relay</text>
  <text x="70" y="140" class="range-label">direct range</text>
  <text x="490" y="140" class="range-label">2 hops from teacher</text>
</svg>`;

const EVT_LABEL = {
  originated: "sent",
  delivered: "delivered",
  duplicate: "duplicate suppressed",
  ttl_expired: "dropped (TTL exhausted)",
};

export async function renderMesh(view, appState) {
  view.append(
    el("section", {},
      el("h2", { style: "margin:0 0 4px" }, "📡 Offline Mesh"),
      el("p", { style: "color:var(--ink-soft);margin:0 0 14px" },
        "Relay lessons, homework and school notices between nearby devices with no internet.")),
  );

  let status;
  try {
    status = await fetchMeshStatus();
  } catch (err) {
    view.append(errorNote(err));
    return;
  }

  /* --- what transport are we actually on? (the honesty panel) --- */
  if (status.simulation_banner) {
    view.append(el("div", { class: "sim-banner" }, status.simulation_banner));
  }
  const ble = (status.transports || []).find((t) => t.mode !== "simulation");
  const bleCard = el("div", { class: "card transport-note" });
  if (ble) {
    bleCard.append(
      el("p", { style: "margin:0 0 4px" },
        badge(ble.available ? `✓ ${ble.name}` : "✗ " + (ble.name || "Bluetooth LE"), ble.available ? "local" : "machine"),
        " ", el("b", {}, "Native Bluetooth transport"),
        ble.available ? "" : " unavailable — demo simulation available."));
    bleCard.append(el("p", { style: "margin:0;color:var(--ink-soft);font-size:13px" },
      ble.reason || ble.note || ""));
  }
  view.append(bleCard);

  /* --- layout: topology + inbox | compose + timeline --- */
  const grid = el("div", { class: "mesh-grid" });
  const leftCol = el("div", {});
  const rightCol = el("div", {});
  grid.append(leftCol, rightCol);

  /* --- topology + node inboxes --- */
  const topoCard = el("div", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Classroom topology"),
    el("p", { style: "color:var(--ink-soft);font-size:13px;margin:0 0 6px" },
      "Click a device to open its inbox."));
  const topoWrap = el("div", {});
  topoWrap.innerHTML = SVG_TOPOLOGY;   // static markup, no user data inside
  const inboxCard = el("div", { class: "card" }, el("h3", { style: "margin-top:0" }, "Inbox"));

  let selectedNode = "student-b";
  const paintSelected = () => {
    topoWrap.querySelectorAll(".mnode").forEach((n) =>
      n.classList.toggle("selected", n.dataset.node === selectedNode));
    inboxCard.querySelectorAll("h3")[0].replaceChildren(
      el("span", {}, "Inbox — " + selectedNode));
  };
  topoWrap.querySelectorAll(".mnode").forEach((n) =>
    n.addEventListener("click", () => { selectedNode = n.dataset.node; paintSelected(); loadInbox(); }));
  topoCard.append(topoWrap);
  leftCol.append(topoCard, inboxCard);

  async function loadInbox() {
    inboxCard.innerHTML = "";
    inboxCard.append(el("h3", { style: "margin-top:0" }, "Inbox — " + selectedNode));
    try {
      const data = await getJSON(`/api/mesh/inbox?node=${encodeURIComponent(selectedNode)}`);
      if (!data.messages.length) {
        inboxCard.append(el("p", { style: "color:var(--ink-soft)" }, "Empty — send a message."));
        return;
      }
      for (const m of data.messages) {
        inboxCard.append(el("div", { class: "inbox-msg" },
          el("p", { class: "inbox-label" }, m.label || "Received via mesh"),
          m.payload && m.payload.title ? el("p", { class: "hindi-text" }, m.payload.title) : null,
          el("p", { class: m.language === "sat" ? "santali-text" : "hindi-text" },
            (m.payload && m.payload.text) || ""),
          el("p", { class: "inbox-meta" },
            `${m.type} · from ${m.sender_id} · hops: ${m.received_hop_count} · ttl left: ${m.ttl} · ${String(m.timestamp).slice(11, 19)}`),
          el("p", { class: "inbox-meta" }, "path: " + (m.path || []).join(" → "))));
      }
    } catch (err) {
      inboxCard.append(errorNote(err));
    }
  }

  /* --- compose --- */
  const senderSel = el("select", {},
    el("option", { value: "teacher" }, "teacher"),
    el("option", { value: "student-a" }, "student A"),
    el("option", { value: "student-b" }, "student B"));
  const typeSel = el("select", {},
    ...(status.message_types || []).map((t) => el("option", { value: t }, t)));
  const langSel = el("select", {},
    el("option", { value: "hi" }, "Hindi"),
    el("option", { value: "sat" }, "Santali (ᱥᱟᱱᱛᱟᱲᱤ)"));
  const ttlInput = el("input", { type: "number", value: "5", min: "1", max: "5", style: "width:70px" });
  const titleInput = el("input", { type: "text", placeholder: "title (optional)" });
  const textInput = el("textarea", { rows: "2" });
  textInput.value = "कल गणित की कॉपी साथ लाईये।";

  const sendBtn = el("button", { class: "btn primary", type: "submit" }, "Send over mesh");
  const compose = el("form", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Compose"),
    el("div", { class: "form-grid" },
      el("label", { class: "field" }, el("span", {}, "From"), senderSel),
      el("label", { class: "field" }, el("span", {}, "Type"), typeSel),
      el("label", { class: "field" }, el("span", {}, "Language"), langSel),
      el("label", { class: "field" }, el("span", {}, "TTL (hops to live)"), ttlInput)),
    el("label", { class: "field" }, el("span", {}, "Title"), titleInput),
    el("label", { class: "field" }, el("span", {}, "Text"), textInput),
    sendBtn,
    el("p", { style: "font-size:12.5px;color:var(--ink-soft);margin-bottom:0" },
      "Each relay costs 1 TTL. Nodes drop messages they have already seen (by id)."));

  /* --- timeline --- */
  const timeline = el("div", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Relay timeline"));
  const evtList = el("div", { class: "event-timeline" });
  timeline.append(evtList);
  const resetBtn = el("button", { class: "btn ghost" }, "Reset mesh session");
  resetBtn.addEventListener("click", async () => {
    try {
      await postForm("/api/mesh/reset", form({}));
      evtList.innerHTML = "";
      loadInbox();
      toast("Mesh session reset — seen-id lists cleared.");
    } catch (err) { toast("Reset failed: " + err.message); }
  });
  timeline.append(resetBtn);

  rightCol.append(compose, timeline);

  const addEvent = (ev) => {
    const row = el("div", { class: "evt evt-" + ev.event },
      el("span", { class: "evt-kind" }, EVT_LABEL[ev.event] || ev.event),
      el("span", { class: "evt-path" },
        `${ev.from_node ? ev.from_node + " → " : ""}${ev.to_node}`),
      ev.hop_count !== undefined ? el("span", { class: "evt-hop" }, `hop ${ev.hop_count}`) : null,
      ev.ttl_remaining !== undefined ? el("span", { class: "evt-ttl" }, `ttl ${ev.ttl_remaining}`) : null,
      el("span", { class: "evt-id" }, "#" + String(ev.message_id || "").slice(0, 6)));
    evtList.append(row);
    row.scrollIntoView({ block: "nearest" });
  };

  compose.addEventListener("submit", async (e) => {
    e.preventDefault();
    sendBtn.disabled = true;
    try {
      const data = await postForm("/api/mesh/send", form({
        sender_id: senderSel.value,
        type: typeSel.value,
        language: langSel.value,
        title: titleInput.value,
        text: textInput.value,
        ttl: ttlInput.value,
      }));
      toast(`Sent — ${data.message.id.slice(0, 8)} relayed through the mesh.`);
      selectedNode = "student-b";
      paintSelected();
      loadInbox();
    } catch (err) {
      toast("Send failed: " + err.message);
    } finally {
      sendBtn.disabled = false;
    }
  });

  /* --- live events: WebSocket first, existing history second --- */
  try {
    const data = await getJSON("/api/mesh/events");
    for (const ev of data.events || []) addEvent(ev);
  } catch { /* history is nice-to-have; live socket covers the rest */ }

  let ws = null;
  const openSocket = () => {
    if (ws && ws.readyState <= 1) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/mesh`);
    ws.onmessage = (m) => {
      try { addEvent(JSON.parse(m.data).data); } catch { /* not our frame */ }
    };
  };
  openSocket();

  paintSelected();
  await loadInbox();
  view.append(grid);
}
