"""Tests for the 25-req/min cap - the project's own hard constraint.

The limiter must hold under a burst, release only as the window slides, and
the middleware must cap /api/* while leaving static files alone.
"""

import asyncio

from backend import config
from backend.ratelimit import SlidingWindowLimiter, as_fastapi_middleware


def test_25_allowed_then_26th_blocked():
    lim = SlidingWindowLimiter(limit=config.RATE_LIMIT_PER_MIN)
    for _ in range(config.RATE_LIMIT_PER_MIN):
        ok, retry = lim.acquire()
        assert ok, "the first 25 requests in a window must all pass"
    ok, retry = lim.acquire()
    assert not ok, "request 26 within the same window must be refused"
    assert retry > 0


def test_window_slides():
    # Tiny window so the test is fast; the arithmetic is the same at 60 s.
    lim = SlidingWindowLimiter(limit=2, window_s=0.4)
    assert lim.acquire()[0]
    assert lim.acquire()[0]
    assert not lim.acquire()[0], "budget exhausted inside the window"
    import time
    time.sleep(0.45)
    assert lim.acquire()[0], "an old hit must have slid out of the window"


def test_wait_for_slot_blocks_until_free():
    lim = SlidingWindowLimiter(limit=1, window_s=0.3)
    assert lim.acquire()[0]
    import time
    t0 = time.monotonic()
    lim.wait_for_slot()
    assert time.monotonic() - t0 >= 0.2, "wait_for_slot must respect the window"


def test_snapshot_reports_usage():
    lim = SlidingWindowLimiter(limit=config.RATE_LIMIT_PER_MIN)
    lim.acquire()
    lim.acquire()
    snap = lim.snapshot()
    assert snap["limit_per_min"] == config.RATE_LIMIT_PER_MIN
    assert snap["used_in_window"] == 2


def test_middleware_caps_api_but_not_static():
    lim = SlidingWindowLimiter(limit=2)

    async def ok_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def call(path):
        captured = []

        async def send(msg):
            captured.append(msg)

        mw = as_fastapi_middleware(lim)(ok_app)
        await mw({"type": "http", "path": path, "method": "GET"}, receive, send)
        return captured[0]["status"]

    assert asyncio.run(call("/api/status")) == 200
    assert asyncio.run(call("/api/voice/tts")) == 200
    assert asyncio.run(call("/api/status")) == 429, "third /api hit must be capped"
    assert asyncio.run(call("/static/app.js")) == 200, "static assets stay uncapped"
    assert asyncio.run(call("/")) == 200, "the page itself stays uncapped"
