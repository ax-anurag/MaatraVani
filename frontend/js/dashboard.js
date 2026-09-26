/* Dashboard: three module cards + honest system status. */

import { el, badge, escapeHtml } from "./ui.js";
import { fetchStatus } from "./api.js";

export async function renderDashboard(view, appState) {
  if (!appState.status) {
    try { appState.status = await fetchStatus(); } catch { /* pill already says it */ }
  }
  const s = appState.status;

  view.append(
    el("section", { class: "hero" },
      el("h1", {}, "MAATA", el("b", {}, "VANI")),
      el("p", { class: "tagline" }, "Breaking language and connectivity barriers in education."),
      el("p", { class: "tagline" }, "एक हिंदी-भाषी शिक्षक, संथाली-भाषी बच्चों की कक्षा।"),
      el("p", { class: "olchiki-sample", title: "Santali, written in Ol Chiki" }, "ᱥᱟᱱᱛᱟᱲᱤ")
    )
  );

  const grid = el("div", { class: "module-grid" });
  const cards = [
    { route: "#/voice", icon: "🎙", title: "Voice Translator",
      desc: "Hindi ↔ Santali. Speak, translate and understand — fully local models.",
      go: "Open translator →" },
    { route: "#/materials", icon: "📚", title: "Study Materials",
      desc: "Bilingual FLN lessons, printable worksheets and visual flashcards.",
      go: "Create materials →" },
    { route: "#/mesh", icon: "📡", title: "Offline Mesh",
      desc: "Share lessons, homework and school notices without internet.",
      go: "Open mesh →" },
  ];
  for (const c of cards) {
    grid.append(
      el("div", { class: "card module-card clickable", onclick: () => (location.hash = c.route) },
        el("div", { class: "icon" }, c.icon),
        el("h2", {}, c.title),
        el("p", {}, c.desc),
        el("span", { class: "go" }, c.go))
    );
  }
  view.append(grid);

  /* --- honest status card: exactly what the backend reports --- */
  const statusCard = el("div", { class: "card" });
  statusCard.append(el("h2", { style: "margin-top:0" }, "System status"));

  if (!s) {
    statusCard.append(el("p", {}, "Backend not reachable — is the server running? (scripts/run_dev.sh)"));
  } else {
    const tr = s.engines.translation || {};
    const rows = el("div", {});
    const mk = (name, ok, note) =>
      el("p", {}, badge(ok ? "✓ available" : "✗ missing", ok ? "local" : "machine"),
        " ", el("b", {}, name), note ? ` — ${note}` : "");
    rows.append(
      mk(`Translation (NLLB-200 600M, int8)`, tr.nllb_available, tr.nllb_available ? "Hindi ↔ Santali, offline" : "run scripts/download_models.py"),
      mk("ASR — Vosk small Hindi", (s.engines.asr || []).some(e => e.available && e.engine.includes("vosk")), "fast, offline"),
      mk("ASR — faster-whisper small", (s.engines.asr || []).some(e => e.available && e.engine.includes("whisper")), "higher accuracy, offline"),
      mk(`TTS — espeak-ng ${((s.engines.tts || [])[0]?.voices?.sat) ? "(Santali voice present)" : "(Santali voice missing)"}`,
        !!((s.engines.tts || [])[0]?.voices?.sat), "genuine but robotic Santali synthesis"),
    );
    statusCard.append(rows);

    statusCard.append(el("h3", {}, "Languages"));
    const chips = el("div", { class: "lang-chips" });
    for (const [code, lang] of Object.entries(s.languages || {})) {
      chips.append(badge(
        `${lang.name}${lang.script ? " · " + lang.script : ""}`,
        lang.status === "available" ? "local" : "planned"));
      if (lang.status !== "available") {
        chips.append(el("span", { style: "font-size:12px;color:var(--ink-faint)" }, "Planned / Future Language"));
      }
    }
    statusCard.append(chips);

    statusCard.append(el("p", { style: "margin-bottom:0;color:var(--ink-soft);font-size:13.5px" }, ""));
  }
  view.append(statusCard);
}
