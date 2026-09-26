/* App shell: tiny hash router + shared state (status). No framework, no
   build step - this whole frontend is plain ES modules served statically. */

import { renderDashboard } from "./dashboard.js";
import { renderVoice } from "./voice.js";
import { renderMaterials } from "./materials.js";
import { renderMesh } from "./mesh.js";
import { fetchStatus } from "./api.js";
import { toast } from "./ui.js";

const view = document.getElementById("view");
const routes = {
  "/": renderDashboard,
  "/voice": renderVoice,
  "/materials": renderMaterials,
  "/mesh": renderMesh,
};

export const appState = {
  status: null,          // last /api/status payload
  backendReachable: false,
};

export async function refreshStatus() {
  try {
    appState.status = await fetchStatus();
    appState.backendReachable = true;
  } catch (err) {
    appState.backendReachable = false;
    if (!err.rateLimited) appState.status = null;
  }
  paintStatusPill();
}

function paintStatusPill() {
  const pill = document.getElementById("status-pill");
  const label = document.getElementById("status-label");
  const s = appState.status;
  pill.className = "status-pill";

  if (!appState.backendReachable) {
    pill.classList.add("offline");
    label.textContent = "BACKEND UNREACHABLE";
    return;
  }
  if (s && s.offline_mode) {
    pill.classList.add("offline");
    label.textContent = "OFFLINE · LOCAL MODELS ACTIVE";
    return;
  }
  if (navigator.onLine) {
    pill.classList.add("online");
    label.textContent = "ONLINE";
  } else {
    pill.classList.add("offline");
    label.textContent = "OFFLINE · LOCAL MODELS ACTIVE";
  }
}

async function route() {
  const hash = (location.hash || "#/").replace(/^#/, "") || "/";
  const render = routes[hash] || renderDashboard;
  document.querySelectorAll("nav.mainnav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.route === (routes[hash] ? hash : "/"));
  });
  view.innerHTML = "";
  await render(view, appState);
}

window.addEventListener("hashchange", route);
window.addEventListener("online", paintStatusPill);
window.addEventListener("offline", paintStatusPill);

document.getElementById("footer-note").textContent =
  "MaatraVani · offline-first proof of concept";

refreshStatus().then(route);
