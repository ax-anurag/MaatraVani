"""Global API rate limiting.

Hard cap, per the project's own constraint: at most RATE_LIMIT_PER_MIN
(default 25) API requests in any rolling 60-second window, across all
/api/* endpoints combined. Sliding window, so there is no way to game it
with a burst. When the window is exhausted the caller gets a 429 and simply
waits — the cap holds no matter how long that takes.

The same primitive throttles any *outbound* provider call (e.g. the optional
Bhashini fallback), so the app can never hammer an external API either.
"""

import time
from collections import deque
from threading import Lock


class SlidingWindowLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = limit
        self.window_s = window_s
        self._hits: deque[float] = deque()
        self._lock = Lock()

    def acquire(self) -> tuple[bool, float]:
        """Try to consume one slot. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            while self._hits and now - self._hits[0] > self.window_s:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                retry = max(0.05, self.window_s - (now - self._hits[0]))
                return False, retry
            self._hits.append(now)
            return True, 0.0

    def wait_for_slot(self, poll_s: float = 0.25) -> None:
        """Blocking variant used for outbound calls: waits as long as needed."""
        while True:
            allowed, retry = self.acquire()
            if allowed:
                return
            time.sleep(min(retry, poll_s) if retry > poll_s else poll_s)

    def snapshot(self) -> dict:
        """Current budget info, for the status endpoint."""
        now = time.monotonic()
        with self._lock:
            while self._hits and now - self._hits[0] > self.window_s:
                self._hits.popleft()
            return {
                "limit_per_min": self.limit,
                "window_s": self.window_s,
                "used_in_window": len(self._hits),
            }


class OutboundThrottle(SlidingWindowLimiter):
    """Alias to make intent obvious at call sites in the provider code."""


def as_fastapi_middleware(limiter: SlidingWindowLimiter):
    """Starlette middleware that enforces the limiter on /api/* paths only.
    Static assets are not API requests and are deliberately left uncapped.
    """

    from starlette.responses import JSONResponse

    class RateLimitMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http" and scope["path"].startswith("/api/"):
                allowed, retry_after = limiter.acquire()
                if not allowed:
                    response = JSONResponse(
                        {
                            "error": "rate_limited",
                            "detail": (
                                f"API budget of {limiter.limit} requests/min is "
                                f"exhausted; retry after {retry_after:.1f} s."
                            ),
                        },
                        status_code=429,
                        headers={"Retry-After": f"{int(retry_after) + 1}"},
                    )
                    await response(scope, receive, send)
                    return
            await self.app(scope, receive, send)

    return RateLimitMiddleware
