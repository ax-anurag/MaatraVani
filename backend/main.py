"""MaatraVani application assembly: FastAPI app + rate-limit middleware +
static frontend serving. Run with:

    uvicorn backend.main:app --host 127.0.0.1 --port 8000

Offline demo: set MATR_OFFLINE=1 (or use scripts/run_dev.sh --offline) and
the app refuses every network egress path while fully serving the UI, the
translation pipeline, materials generation and the mesh simulation.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .api.routes import router
from .ratelimit import SlidingWindowLimiter, as_fastapi_middleware

# One global budget for the whole API, per the project constraint:
# hard cap of 25 requests per rolling 60 s, no matter the time it takes.
API_LIMITER = SlidingWindowLimiter(limit=config.RATE_LIMIT_PER_MIN)

app = FastAPI(title="MaatraVani", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(as_fastapi_middleware(API_LIMITER))

app.include_router(router)

# The frontend is plain static files served by the same process - one
# server, no CDN, no internet requirement.
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="static")


@app.on_event("startup")
async def _report_state():
    from .engines import snapshot

    state = snapshot()
    print(f"maatravani 0.1.0  |  offline_mode={config.OFFLINE_MODE}")
    print(f"api rate limit: {config.RATE_LIMIT_PER_MIN} req/min (global, /api/*)")
    for area in ("translation", "asr", "tts"):
        blocks = state.get(area, [])
        if isinstance(blocks, dict):
            blocks = [blocks]
        for b in blocks:
            print(f"  {area:<12} {b.get('engine', b.get('name', '?')):<34} "
                  f"{'available' if b.get('available') else 'MISSING: ' + str(b.get('reason'))[:60]}")
    if config.FRONTEND_DIR.exists():
        print(f"frontend: {config.FRONTEND_DIR}")
    else:
        print("frontend: (directory missing)")
