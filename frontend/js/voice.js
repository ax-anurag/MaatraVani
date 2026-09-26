/* Voice Translator page - the flagship demo flow.

One push-to-talk recording -> ONE POST /api/voice/translate -> transcript,
Ol Chiki translation, Santali audio, and the real measured latencies.
Text-input mode exists for machines without a microphone (WSL2's Linux
side has none; the Windows browser does) and for scripted tests. */

import { el, badge, localBadge, latencyTable, reviewWarning, errorNote, toast } from "./ui.js";
import { postForm, form } from "./api.js";
import { WavRecorder, playB64 } from "./audio.js";

export async function renderVoice(view, appState) {
  const state = { src: "hi", tgt: "sat" };

  const header = el("div", {},
    el("h2", { style: "margin:0 0 4px" }, "🎙 Voice Translator"),
    el("p", { style: "color:var(--ink-soft);margin:0 0 18px" },
      "Speak Hindi — the class hears Santali. Push-to-talk, measured end-to-end."));

  /* --- direction row --- */
  const langNames = { hi: "Hindi", sat: "Santali", hoc: "Ho", muq: "Mundari" };
  const mkLangBox = (side) => {
    const box = el("div", { class: "lang-box" },
      side === "src" ? langNames[state.src] : langNames[state.tgt]);
    if (side === "src" && state.src === "sat" || side === "tgt" && state.tgt === "sat") {
      box.append(el("div", { class: "olck", style: "font-size:13px;color:var(--green)" }, "ᱥᱟᱱᱛᱟᱲᱤ"));
    }
    return box;
  };
  const directionRow = el("div", { class: "voice-direction" });
  const renderDirection = () => {
    directionRow.innerHTML = "";
    directionRow.append(
      mkLangBox("src"),
      el("button", { class: "swap-btn", title: "Swap languages",
        onclick: () => { [state.src, state.tgt] = [state.tgt, state.src]; renderAll(); } }, "⇄"),
      mkLangBox("tgt"));
  };

  /* --- mic --- */
  const micWrap = el("div", { class: "mic-wrap" });
  const results = el("div", { class: "results" });
  const recorder = WavRecorder.supported ? new WavRecorder() : null;
  let audioEl = null;

  const renderMic = () => {
    micWrap.innerHTML = "";
    if (!recorder) {
      micWrap.append(el("p", { class: "mic-hint" },
        "Microphone not available in this browser context — use text mode below."));
      return;
    }
    const speakingSantali = state.src === "sat";
    const btn = el("button", {
      class: "mic-btn" + (recorder.recording ? " rec" : ""),
      title: "Push to talk",
      onclick: async () => {
        if (!recorder.recording) {
          try { await recorder.start(); }
          catch (e) { toast("Microphone permission denied: " + e.message); return; }
          renderMic();
        } else {
          const wav = await recorder.stop();
          renderMic();
          if (wav) await runPipeline(wav);
        }
      },
    }, recorder.recording ? "■" : "🎙");
    micWrap.append(btn,
      el("p", { class: "mic-hint" },
        recorder.recording
          ? el("b", {}, "Listening… click to stop")
          : el("span", {}, "🎙 ", el("b", {}, `SPEAK ${langNames[state.src].toUpperCase()}`)),
        "  ·  16 kHz mono, encoded locally in your browser"),
    );
    if (speakingSantali) {
      micWrap.append(el("p", { class: "mic-hint", style: "color:var(--danger)" },
        "Heads-up: offline Santali speech recognition does not exist today. " +
        "This direction needs the (optional, credentials-gated) Bhashini fallback — " +
        "the backend will say so honestly if it is not configured."));
    }
  };

  /* --- text mode --- */
  const textForm = el("form", {},
    el("label", { class: "field" },
      el("span", {}, `Type ${langNames[state.src]} instead`),
      el("input", { type: "text", id: "voice-text", placeholder: state.src === "hi" ? "आज हम जानवरों के नाम सीखेंगे।" : "" })),
    el("button", { class: "btn", type: "submit" }, "Translate text →"));
  textForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = document.getElementById("voice-text").value.trim();
    if (!text) return;
    results.innerHTML = "";
    try {
      const data = await postForm("/api/voice/translate-text",
        form({ text, src: state.src, tgt: state.tgt, speak: "true" }));
      paintTextResult(data);
    } catch (err) { results.append(errorNote(err)); }
  });

  /* --- pipeline run (voice) --- */
  async function runPipeline(wavBlob) {
    results.innerHTML = "";
    results.append(el("p", { class: "mic-hint" }, "Running local pipeline…"));
    try {
      const data = await postForm("/api/voice/translate",
        form({ audio: wavBlob, src: state.src, tgt: state.tgt }));
      paintFullResult(data);
    } catch (err) {
      results.innerHTML = "";
      results.append(errorNote(err));
    }
  }

  function paintTextResult(data) {
    results.innerHTML = "";
    // The typed text is still sitting in the input field, so echoing it back
    // would be noise; show the translation (and audio when TTS worked).
    const tgtCard = el("div", { class: "card result-card santali-card" },
      el("h3", {}, `${langNames[state.tgt]} — ${data.script || ""} ` , localBadge()),
      el("div", { class: state.tgt === "sat" ? "santali-text" : "hindi-text" }, data.text));
    if (data.source) {
      tgtCard.append(el("p", { style: "font-size:12.5px;color:var(--ink-soft)" },
        "engine: ", el("b", {}, data.engine), ` · source: ${data.source}`));
    }
    if (data.audio_b64) {
      tgtCard.append(el("button", { class: "btn play-btn", onclick: () => { audioEl = playB64(data.audio_b64); } }, "▶ Play"));
      if (data.tts_note || data.tts_voice) {
        tgtCard.append(el("p", { style: "font-size:12.5px;color:var(--ink-soft)" },
          "🔊 ", el("b", {}, data.tts_voice || ""), data.tts_note ? " — " + data.tts_note : ""));
      }
    } else if (data.tts_unavailable) {
      tgtCard.append(errorNote(new Error(data.tts_error || "Santali TTS model unavailable.")));
    }
    if (data.review_warning) tgtCard.append(reviewWarning(data.review_warning));
    results.append(tgtCard);
  }

  function paintFullResult(data) {
    results.innerHTML = "";
    const asr = data.stages?.asr || {};
    const tr = data.stages?.translation || {};
    const tts = data.stages?.tts || {};

    const srcCard = el("div", { class: "card result-card" },
      el("h3", {}, `Recognized ${langNames[state.src]} — ${asr.engine || ""}`),
      el("div", { class: state.src === "hi" ? "hindi-text" : "santali-text" },
        asr.text || el("em", {}, "(no speech recognized)")),
      asr.available === false ? errorNote(new Error(asr.error)) : null);
    results.append(srcCard);

    if (!tr.available && tr.error) {
      results.append(errorNote(new Error(tr.error)));
      return;
    }

    const tgtCard = el("div", { class: "card result-card santali-card" },
      el("h3", {}, `${langNames[state.tgt]} — ${tr.script || "Ol Chiki"} ` , localBadge()),
      el("div", { class: state.tgt === "sat" ? "santali-text" : "hindi-text" }, tr.text));
    if (data.audio_b64) {
      tgtCard.append(el("button", { class: "btn play-btn",
        onclick: () => { if (audioEl) audioEl.pause(); audioEl = playB64(data.audio_b64); } },
        "▶ Play Santali"));
      if (tts.note || tts.voice) {
        tgtCard.append(el("p", { style: "font-size:12.5px;color:var(--ink-soft)" },
          "🔊 ", el("b", {}, tts.voice || ""), tts.note ? " — " + tts.note : ""));
      }
    } else if (tts.available === false) {
      tgtCard.append(errorNote(new Error(tts.error || "Santali TTS model unavailable.")));
    }
    if (tr.source) {
      tgtCard.append(el("p", { style: "font-size:12.5px;color:var(--ink-soft)" },
        "engine: ", el("b", {}, tr.engine), ` · source: ${tr.source}`));
    }
    results.append(tgtCard);

    if (data.review_warning) results.append(reviewWarning(data.review_warning));

    const latCard = el("div", { class: "card" }, el("h3", {}, "Measured latency"));
    latCard.append(latencyTable(data.latency || {}, { target: data.target_latency_budget_s || 3.0 }));
    results.append(latCard);

    const actions = el("div", { class: "voice-actions" },
      el("button", { class: "btn ghost", onclick: () => { results.innerHTML = ""; toast("Cleared."); } }, "Clear"),
      el("button", { class: "btn ghost", onclick: () => { [state.src, state.tgt] = [state.tgt, state.src]; renderAll(); } }, "Swap Languages"),
    );
    results.append(actions);
  }

  function renderAll() { renderDirection(); renderMic(); }
  renderAll();

  view.append(header, directionRow, micWrap, el("div", { class: "card" }, textForm), results);
}
