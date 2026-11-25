"""In-memory sliding window limiter. Per-process: correct for ONE api replica.
Move the store to Redis before scaling the API horizontally."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings
from .net import client_ip

_hits: dict[str, deque] = defaultdict(deque)


def hit(key: str, limit: int, window_seconds: int) -> bool:
    """Records a hit; returns False if over the limit."""
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    if len(_hits) > 50000:  # bound memory under a flood of distinct keys
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > window_seconds][:10000]:
            _hits.pop(k, None)
    return True


def limit_key(request: Request) -> str:
    """Signed-in callers are limited per SESSION, not per IP: a whole college can share one campus Wi-Fi address.
    Anonymous callers fall back to the (spoof-resistant) client IP."""
    tok = request.cookies.get("clubos_session")
    return f"s:{tok[:16]}" if tok else f"ip:{client_ip(request)}"


def rate_limit(name: str, limit: int, window_seconds: int, per: str = "session"):
    def dep(request: Request):
        key = limit_key(request) if per == "session" else f"ip:{client_ip(request)}"
        if settings.rate_limit_enabled and not hit(f"{name}:{key}", limit, window_seconds):
            raise HTTPException(429, "Too many requests. Slow down.")
    return dep
