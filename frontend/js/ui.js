/* Small shared UI helpers. */

export function toast(message, ms = 3200) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), ms);
}

/* NB: entity strings are built by concatenation so the source never
   contains a literal "&xxx;" sequence (this repo is written/transferred
   through a pipeline that unescapes them). */
const ENT = {
  "&": "&" + "amp;",
  "<": "&" + "lt;",
  ">": "&" + "gt;",
  '"': "&" + "quot;",
  "'": "&" + "#39;",
};

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ENT[c]);
}

/* Quick element builder: el("div", {class: "x", onclick: fn}, children...) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
}

export const badge = (text, cls = "") => el("span", { class: `badge ${cls}` }, text);

export const localBadge = () => badge("● LOCAL OFFLINE MODEL", "local");

export function latencyTable(latency, { target = 3.0 } = {}) {
  const rows = [
    ["ASR", latency.asr],
    ["Translation", latency.translation],
    ["TTS", latency.tts],
    ["Total", latency.total],
  ];
  const tbl = el("table", { class: "latency-table" });
  for (const [name, val] of rows) {
    if (val === undefined || val === null) continue;
    tbl.append(
      el("tr", { class: name === "Total" ? "total" : "" },
        el("td", {}, name),
        el("td", {}, `${Number(val).toFixed(2)} s`))
    );
  }
  const overBudget = latency.total !== undefined && latency.total > target;
  tbl.append(el("p", { class: "latency-target" },
    overBudget
      ? `Target < ${target} s — measured ${Number(latency.total).toFixed(2)} s (over budget; real measurement, see DEMO.md)`
      : `Target < ${target} s — measured ${Number(latency.total ?? 0).toFixed(2)} s ✓`));
  return tbl;
}

export function reviewWarning(text) {
  return el("div", { class: "badge warning" }, `⚠ ${text || "Machine-generated translation. Please review before classroom use."}`);
}

export function errorNote(err) {
  return el("div", { class: "error-note" }, `✗ ${err.message || err}`);
}
