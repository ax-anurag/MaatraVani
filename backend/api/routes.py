"""HTTP API for MaatraVani.

Design rule: every response tells the truth. Engine failures come back as
{"available": false, "error": ...} on the relevant stage — never as a
silently degraded or invented result. All routes share the global
25-req/min budget enforced in main.py's middleware.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from .. import config
from ..curriculum import flashcards, generator, outcomes, worksheets
from ..engines import snapshot
from ..mesh import MESSAGE_TYPES
# the factory comes from its module, not the package - see the shadowing
# note in backend/mesh/__init__.py
from ..mesh.manager import manager
from ..services import pipeline

router = APIRouter(prefix="/api")


def _ensure_implemented(*codes: str) -> None:
    """Same refusal semantics on every voice route: a planned/future
    language is a 400 ("not implemented"), not a 422 engine crash."""
    for code in codes:
        if code not in config.LANGUAGES:
            raise HTTPException(400, "unknown language code")
        if config.LANGUAGES[code]["status"] != "available":
            raise HTTPException(400, "selected language is planned/future, not implemented")


# ---------------------------------------------------------------- system ---

@router.get("/status")
def status():
    """Powers the status pill + engine badges. Note that we report the
    *server-side* view of connectivity only when it deliberately probes;
    in offline mode we say offline because we refuse to probe anything."""
    mesh = manager()
    return {
        "app": "maatravani",
        "version": "0.1.0",
        "offline_mode": config.OFFLINE_MODE,
        "online": False if config.OFFLINE_MODE else None,  # client infers + backend never probes silently
        "rate_limit": config.RATE_LIMIT_PER_MIN,
        "engines": snapshot(),
        "mesh": mesh.describe(),
    }


@router.get("/languages")
def languages():
    return config.LANGUAGES


# ----------------------------------------------------------------- voice ---

@router.post("/voice/translate")
async def voice_translate(
    audio: UploadFile = File(...),
    src: str = Form("hi"),
    tgt: str = Form("sat"),
):
    _ensure_implemented(src, tgt)
    data = await audio.read()
    if not data:
        raise HTTPException(400, "empty audio upload")
    result = pipeline.run_pipeline(data, src, tgt)
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result


@router.post("/voice/translate-text")
def voice_translate_text(
    text: str = Form(...),
    src: str = Form("hi"),
    tgt: str = Form("sat"),
    speak: bool = Form(False),
):
    _ensure_implemented(src, tgt)
    try:
        return pipeline.translate_text(text.strip(), src, tgt, speak=speak)
    except Exception as err:
        raise HTTPException(422, str(err))


@router.post("/voice/tts")
def voice_tts(text: str = Form(...), lang: str = Form("sat")):
    _ensure_implemented(lang)
    try:
        return pipeline.speak(text.strip(), lang)
    except Exception as err:
        raise HTTPException(422, str(err))


# -------------------------------------------------------------- materials ---

@router.get("/materials/catalog")
def materials_catalog():
    cat = outcomes.catalog()
    return {
        "grades": cat.grades(),
        "subjects": cat.subjects(),
        "topics": cat.topics(),
        "outcomes": cat.data["outcomes"],
        "card_counts": flashcards.CARD_COUNTS,
    }


@router.post("/materials/lesson")
def materials_lesson(
    grade: str = Form("2"),
    subject: str = Form("Foundational Literacy"),
    topic: str = Form("Animals"),
    outcome: str = Form(""),
    target_language: str = Form("sat"),
):
    try:
        req = generator.LessonRequest(
            grade=grade, subject=subject, topic=topic,
            outcome=outcome, target_language=target_language,
        )
        return generator.generate_lesson(req)
    except Exception as err:
        raise HTTPException(422, str(err))


@router.post("/materials/worksheet")
def materials_worksheet(
    grade: str = Form("2"),
    subject: str = Form("Foundational Literacy"),
    topic: str = Form("Animals"),
    outcome: str = Form(""),
):
    try:
        req = generator.LessonRequest(grade=grade, subject=subject, topic=topic,
                                       outcome=outcome)
        lesson = generator.generate_lesson(req)
        # Matching instruction goes through the real translation chain
        # (lexicon first, NLLB second) - never hand-invented Santali.
        instruction_hi = "गतिविधि: सही जोड़े मिलाइए।"
        instruction = {
            "hi": instruction_hi,
            "sat": pipeline.translate_text(instruction_hi, "hi", "sat")["text"],
        }
        pdf_bytes = worksheets.build_worksheet(
            topic=req.topic, grade=req.grade,
            outcome=lesson["outcome"]["hi"], vocabulary=lesson["vocabulary"],
            instruction=instruction,
        )
        config.GENERATED_DIR.mkdir(exist_ok=True)
        name = f"worksheet_{req.topic.lower().replace(' ', '_')}_{req.grade}.pdf"
        path = config.GENERATED_DIR / name
        path.write_bytes(pdf_bytes)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )
    except Exception as err:
        raise HTTPException(422, str(err))


@router.post("/materials/flashcards")
def materials_flashcards(
    grade: str = Form("2"),
    subject: str = Form("Foundational Literacy"),
    topic: str = Form("Animals"),
    count: int = Form(4),
):
    try:
        req = generator.LessonRequest(grade=grade, subject=subject, topic=topic)
        lesson = generator.generate_lesson(req)
        cards = flashcards.build_cards(lesson["vocabulary"], count)
        return {
            "topic": req.topic,
            "count": len(cards),
            "cards": [
                {**c, "svg": flashcards.render_svg(c)} for c in cards
            ],
            "review_warning": lesson["review_warning"],
        }
    except Exception as err:
        raise HTTPException(422, str(err))


@router.post("/materials/flashcards/pdf")
def materials_flashcards_pdf(
    grade: str = Form("2"),
    subject: str = Form("Foundational Literacy"),
    topic: str = Form("Animals"),
    count: int = Form(4),
):
    try:
        req = generator.LessonRequest(grade=grade, subject=subject, topic=topic)
        lesson = generator.generate_lesson(req)
        cards = flashcards.build_cards(lesson["vocabulary"], count)
        pdf_bytes = flashcards.render_pdf(cards, topic=req.topic)
        config.GENERATED_DIR.mkdir(exist_ok=True)
        name = f"flashcards_{req.topic.lower().replace(' ', '_')}.pdf"
        path = config.GENERATED_DIR / name
        path.write_bytes(pdf_bytes)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )
    except Exception as err:
        raise HTTPException(422, str(err))


# ------------------------------------------------------------------ mesh ---

@router.get("/mesh/status")
def mesh_status():
    d = manager().describe()
    d["message_types"] = list(MESSAGE_TYPES)
    return d


@router.get("/mesh/nodes")
def mesh_nodes():
    return {"nodes": manager().nodes()}


@router.get("/mesh/inbox")
def mesh_inbox(node: str = "teacher"):
    return {"node": node, "messages": manager().inbox(node)}


@router.get("/mesh/events")
def mesh_events():
    return {"events": manager().events()}


@router.post("/mesh/reset")
def mesh_reset():
    manager().reset()
    return {"reset": True}


@router.post("/mesh/send")
def mesh_send(
    sender_id: str = Form("teacher"),
    type: str = Form("CLASSROOM_MESSAGE"),
    language: str = Form("hi"),
    text: str = Form(...),
    title: str = Form(""),
    ttl: int = Form(5),
):
    try:
        return manager().send(
            sender_id=sender_id, type_=type, language=language,
            payload={"title": title, "text": text}, ttl=ttl,
        )
    except ValueError as err:
        raise HTTPException(400, str(err))


@router.websocket("/ws/mesh")
async def mesh_ws(ws: WebSocket):
    """Live relay events for the mesh page. One connection for the whole
    session - the frontend never polls (API budget is precious at 25/min)."""
    import asyncio

    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue()

    def on_events(events):
        for e in events:
            queue.put_nowait(e.to_dict())

    manager().subscribe(on_events)
    try:
        while True:
            event = await queue.get()
            await ws.send_json({"event": "mesh", "data": event})
    except WebSocketDisconnect:
        pass
    finally:
        manager()._subscribers.remove(on_events)
