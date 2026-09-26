/* API client.
   The backend implements a request budget to encourage offline-first usage.
   It applies to /api endpoints on a rolling minute basis. So this client never polls, caches catalog
   responses for the session, surfaces 429s to the user instead of hammering
   retries, and does everything it can client-side. */

const cache = new Map();

export async function api(path, options = {}) {
  const opts = { headers: {}, ...options };
  if (opts.body && !(opts.body instanceof FormData) && typeof opts.body === "object") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const resp = await fetch(path, opts);
  if (resp.status === 429) {
    const retry = resp.headers.get("Retry-After") || "60";
    throw Object.assign(
      new Error(`API temporarily unavailable. Wait ${retry}s and try again.`),
      { rateLimited: true, retryAfter: Number(retry) }
    );
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try { detail = (await resp.json()).detail || detail; } catch { /* keep */ }
    throw Object.assign(new Error(detail), { status: resp.status });
  }
  return resp;
}

export async function getJSON(path, { cache: useCache = false } = {}) {
  if (useCache && cache.has(path)) return cache.get(path);
  const data = await (await api(path)).json();
  if (useCache) cache.set(path, data);
  return data;
}

/* POST with FormData; returns parsed JSON (or blob if asked). */
export async function postForm(path, formData, as = "json") {
  const resp = await api(path, { method: "POST", body: formData });
  return as === "blob" ? resp.blob() : resp.json();
}

/* Convenience wrappers used by the pages. */
export const fetchStatus = () => getJSON("/api/status");
export const fetchCatalog = () => getJSON("/api/materials/catalog", { cache: true });
export const fetchMeshStatus = () => getJSON("/api/mesh/status", { cache: true });

export function form(fields) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  return fd;
}
