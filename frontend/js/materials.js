/* Study Materials page - bilingual lesson, printable worksheet, flashcards.

The teacher picks Grade / Subject / Topic / FLN outcome and the backend
generates Hindi + Santali content through the real translation chain
(verified lexicon first, NLLB second). Everything downstream - worksheet
PDF, flashcard SVGs/PDF - is rendered locally with local fonts. */

import { el, badge, localBadge, reviewWarning, errorNote, toast } from "./ui.js";
import { fetchCatalog, postForm, form } from "./api.js";

export async function renderMaterials(view, appState) {
  view.append(
    el("section", {},
      el("h2", { style: "margin:0 0 4px" }, "📚 Study Materials"),
      el("p", { style: "color:var(--ink-soft);margin:0 0 18px" },
        "Bilingual FLN / NIPUN Bharat material — generated locally, reviewed by you before class.")),
  );

  /* --- the one request that feeds every select on the page --- */
  let cat;
  try {
    cat = await fetchCatalog();
  } catch (err) {
    view.append(errorNote(err));
    return;
  }

  /* --- builder form --- */
  const outcomeSel = el("select", {});
  const gradeSel = el("select", {});
  const subjectSel = el("select", {});
  const topicInput = el("input", { type: "text", value: "Animals", list: "topic-list" });
  const topicList = el("datalist", { id: "topic-list" },
    ...cat.topics.map((t) => el("option", { value: t })));
  const langSel = el("select", {},
    el("option", { value: "sat" }, "Santali — ᱥᱟᱱᱛᱟᱲᱤ (Ol Chiki)"),
    el("option", { value: "hoc", disabled: "" }, "Ho — Planned / Future Language"),
    el("option", { value: "muq", disabled: "" }, "Mundari — Planned / Future Language"));

  const fill = (sel, items) => {
    sel.innerHTML = "";
    for (const it of items) sel.append(el("option", { value: it }, it));
  };
  fill(gradeSel, cat.grades);
  fill(subjectSel, cat.subjects);

  const refreshOutcomes = () => {
    const forSubj = cat.outcomes.filter((o) => o.grade === gradeSel.value && o.subject === subjectSel.value);
    outcomeSel.innerHTML = "";
    if (!forSubj.length) outcomeSel.append(el("option", { value: "" }, "(no stored outcome — one will be auto-picked)"));
    for (const o of forSubj) outcomeSel.append(el("option", { value: o.text }, o.text));
  };
  gradeSel.addEventListener("change", refreshOutcomes);
  subjectSel.addEventListener("change", refreshOutcomes);

  const lessonBtn = el("button", { class: "btn primary", type: "submit" }, "Generate Lesson");

  const builder = el("form", { class: "card" },
    el("h3", { style: "margin-top:0" }, "Create lesson"),
    el("div", { class: "form-grid" },
      el("label", { class: "field" }, el("span", {}, "Grade"), gradeSel),
      el("label", { class: "field" }, el("span", {}, "Subject"), subjectSel),
      el("label", { class: "field" }, el("span", {}, "Topic"), topicInput),
      el("label", { class: "field" }, el("span", {}, "Learning outcome (FLN)"), outcomeSel),
      el("label", { class: "field" }, el("span", {}, "Target language"), langSel)),
    el("p", { style: "font-size:12.5px;color:var(--ink-soft)" },
      "Outcomes are a representative NIPUN Bharat FLN subset stored in ",
      el("code", {}, "content/lessons/fln_outcomes.json"),
      " — not an official government copy. The lesson preserves the learning objective; it is not a sentence-by-sentence translation."),
    lessonBtn,
  );
  refreshOutcomes();

  /* --- result area --- */
  const out = el("div", { class: "results" });
  let lastLesson = null;

  const buildReq = () => form({
    grade: gradeSel.value,
    subject: subjectSel.value,
    topic: topicInput.value.trim() || "Animals",
    outcome: outcomeSel.value,
    target_language: langSel.value,
  });

  builder.addEventListener("submit", async (e) => {
    e.preventDefault();
    lessonBtn.disabled = true;
    lessonBtn.textContent = "Generating…";
    out.innerHTML = "";
    try {
      lastLesson = await postForm("/api/materials/lesson", buildReq());
      paintLesson(lastLesson);
    } catch (err) {
      out.append(errorNote(err));
    } finally {
      lessonBtn.disabled = false;
      lessonBtn.textContent = "Generate Lesson";
    }
  });

  function biLine(hi, sat, verified) {
    return el("div", { class: "bi-line" },
      el("div", { class: "hi hindi-text" }, hi),
      el("div", { class: "sat santali-text" }, sat,
        verified ? badge("✓ verified entry", "local") : badge("machine", "machine")));
  }

  function paintLesson(lesson) {
    out.innerHTML = "";

    out.append(el("div", { class: "card" },
      el("h3", { style: "margin-top:0" },
        `${lesson.title_hi} · ${lesson.topic}`),
      el("p", { class: "santali-text", style: "margin:2px 0" }, lesson.title_sat),
      el("p", { style: "margin:6px 0 4px;color:var(--ink-soft);font-size:13px" },
        `Grade ${lesson.grade} · ${lesson.subject} · target: ${lesson.target_language}`),
      el("p", { style: "font-size:13px;color:var(--ink-soft)" },
        "Learning outcome: ", el("b", {}, lesson.outcome.hi)),
      el("p", { class: "santali-text", style: "font-size:13px;margin:2px 0 8px" },
        lesson.outcome.sat, " ",
        lesson.outcome.verified ? badge("✓ verified", "local") : badge("machine", "machine")),
      reviewWarning(lesson.review_warning)));

    const scriptCard = el("div", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Lesson script"));
    for (const line of lesson.script || []) scriptCard.append(biLine(line.hi, line.sat, line.verified));
    out.append(scriptCard);

    const actCard = el("div", { class: "card" },
      el("h3", { style: "margin-top:0" }, `Activity — ${lesson.activity.name.hi}`));
    for (const step of lesson.activity.steps || []) actCard.append(biLine(step.hi, step.sat, step.verified));
    out.append(actCard);

    const asCard = el("div", { class: "card" }, el("h3", { style: "margin-top:0" }, "Assessment"));
    for (const a of lesson.assessment || []) {
      asCard.append(biLine(a.question.hi, a.question.sat, a.question.verified));
      if (a.answer_hi) {
        asCard.append(el("p", { style: "font-size:13px;color:var(--ink-soft);margin:0 0 8px" },
          "expected answer: ", el("b", { class: "hindi-text" }, a.answer_hi),
          " / ", el("b", { class: "santali-text" }, a.answer_sat)));
      }
    }
    out.append(asCard);

    if ((lesson.vocabulary || []).length) {
      const vocab = el("div", { class: "card" },
        el("h3", { style: "margin-top:0" }, "Vocabulary"));
      const tbl = el("table", { class: "vocab-table" },
        el("tr", {}, el("th", {}, "हिन्दी"), el("th", {}, "ᱥᱟᱱᱛᱟᱲᱤ"), el("th", {}, "")));
      for (const w of lesson.vocabulary) {
        tbl.append(el("tr", {},
          el("td", { class: "hindi-text" }, w.hi),
          el("td", { class: "santali-text" }, w.sat),
          el("td", {}, w.verified ? badge("✓ verified", "local") : badge("machine", "machine"))));
      }
      vocab.append(tbl);
      out.append(vocab);
    }

    /* worksheet + flashcard actions need a lesson first */
    const actions = el("div", { class: "card" },
      el("h3", { style: "margin-top:0" }, "Printables"),
      el("p", { style: "color:var(--ink-soft)" }, "Generated locally as PDF (fpdf2 + uharfbuzz text shaping for both scripts)."));
    const wsBtn = el("button", { class: "btn" }, "Generate Worksheet PDF");
    wsBtn.addEventListener("click", async () => {
      wsBtn.disabled = true;
      try {
        const blob = await postForm("/api/materials/worksheet", buildReq(), "blob");
        const url = URL.createObjectURL(blob);
        const a = el("a", { href: url, download: `worksheet_${lesson.topic.toLowerCase().replace(/ /g, "_")}.pdf` });
        document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
        toast("Worksheet PDF downloaded (also saved under generated/).");
      } catch (err) { out.append(errorNote(err)); }
      finally { wsBtn.disabled = false; }
    });
    actions.append(wsBtn, el("div", { style: "height:10px" }));

    /* flashcards: 1 / 4 / 8 */
    const countSel = el("select", {},
      ...cat.card_counts.map((n) => el("option", { value: String(n) }, `${n} card${n > 1 ? "s" : ""}`)));
    const fcBtn = el("button", { class: "btn" }, "Generate Flashcards");
    const fcPdfBtn = el("button", { class: "btn ghost", disabled: "" }, "Download PDF");
    const fcGrid = el("div", { class: "flashcard-grid" });
    let haveCards = false;

    fcBtn.addEventListener("click", async () => {
      fcBtn.disabled = true;
      try {
        const data = await postForm("/api/materials/flashcards", form({
          grade: gradeSel.value, subject: subjectSel.value,
          topic: topicInput.value.trim() || "Animals", count: countSel.value,
        }));
        fcGrid.innerHTML = "";
        for (const c of data.cards) {
          const wrap = el("div", { class: "flashcard" });
          wrap.innerHTML = c.svg;   // server-rendered SVG, our own markup
          fcGrid.append(wrap);
        }
        haveCards = true;
        fcPdfBtn.disabled = false;
        fcGrid.append(el("p", { style: "font-size:12.5px;color:var(--ink-soft)" },
          "Illustrations use locally available emoji glyphs — no image-generation API is involved."));
      } catch (err) { out.append(errorNote(err)); }
      finally { fcBtn.disabled = false; }
    });
    fcPdfBtn.addEventListener("click", async () => {
      if (!haveCards) return;
      fcPdfBtn.disabled = true;
      try {
        const blob = await postForm("/api/materials/flashcards/pdf", form({
          grade: gradeSel.value, subject: subjectSel.value,
          topic: topicInput.value.trim() || "Animals", count: countSel.value,
        }), "blob");
        const url = URL.createObjectURL(blob);
        const a = el("a", { href: url, download: `flashcards_${lesson.topic.toLowerCase().replace(/ /g, "_")}.pdf` });
        document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
        toast("Flashcards PDF downloaded (also saved under generated/).");
      } catch (err) { out.append(errorNote(err)); }
      finally { fcPdfBtn.disabled = false; }
    });

    actions.append(el("div", { class: "form-grid" },
      el("label", { class: "field" }, el("span", {}, "Flashcards"), countSel),
      el("label", { class: "field" }, el("span", {}, " "), fcBtn),
      el("label", { class: "field" }, el("span", {}, " "), fcPdfBtn)));
    out.append(actions, el("div", { class: "card" }, fcGrid));
  }

  view.append(builder, topicList, out);
}
