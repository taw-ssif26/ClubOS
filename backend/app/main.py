import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import models  # noqa: F401 - register tables
from .config import settings
from .db import Base, SessionLocal, engine
from .deps import COOKIE
from .net import client_ip
from .ratelimit import hit
from .routers import account, admin, auth, clubs, comms, content, discover, events, ops, reviews, site, users
from .seed import seed


class JsonFormatter(logging.Formatter):
    def format(self, record):
        d = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in ("request_id", "method", "path", "status", "ms", "ip"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d)


_h = logging.StreamHandler()
_h.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_h], force=True)
log = logging.getLogger("clubos")

if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.05, send_default_pii=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.cookie_secure:  # production guard rails
        if len(settings.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be set to at least 32 random characters in production")
        if not settings.smtp_host:
            log.warning("SMTP_HOST is empty: verification and confirmation emails will NOT be delivered")
    if settings.auto_create_tables:
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)  # inserts missing default plans/copy only; never overwrites admin edits
    yield


_prod = settings.cookie_secure  # production: no interactive docs / schema (a free endpoint map for attackers)
app = FastAPI(title="ClubOS API", version="0.2.0", lifespan=lifespan,
              docs_url=None if _prod else "/docs", redoc_url=None if _prod else "/redoc", openapi_url=None if _prod else "/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

ALLOWED_ORIGINS = {o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()} | {settings.base_url.rstrip("/")}
UNSAFE = ("POST", "PUT", "PATCH", "DELETE")


@app.middleware("http")
async def guard(request: Request, call_next):
    """Request id, CSRF origin check, global write limiter, access log, safe 500s, security headers."""
    rid = request.headers.get("x-request-id", "")[:40] or uuid.uuid4().hex[:16]
    ip = client_ip(request)
    t0 = time.perf_counter()
    if request.method in UNSAFE:
        origin = request.headers.get("origin")
        if request.cookies.get(COOKIE) and origin and origin.rstrip("/") not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403, headers={"X-Request-ID": rid})
        tok = request.cookies.get(COOKIE)
        # per-session budget for signed-in users; a generous per-IP ceiling (campus NAT!) stops anonymous floods
        if settings.rate_limit_enabled and not (hit(f"writes:ip:{ip}", 1200, 60) and (hit(f"writes:s:{tok[:16]}", 120, 60) if tok else True)):
            return JSONResponse({"detail": "Too many requests. Slow down."}, status_code=429, headers={"X-Request-ID": rid})
    try:
        resp = await call_next(request)
    except Exception:  # noqa: BLE001
        log.exception("unhandled error", extra={"request_id": rid, "method": request.method, "path": request.url.path, "ip": ip})
        resp = JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500)
    resp.headers["X-Request-ID"] = rid
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger UI needs scripts; the API itself serves only JSON/SVG
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.cookie_secure:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path != "/health":
        log.info("request", extra={"request_id": rid, "method": request.method, "path": request.url.path, "status": resp.status_code,
                                   "ms": round((time.perf_counter() - t0) * 1000), "ip": ip})
    return resp


os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

for r in (auth.router, account.router, users.router, clubs.router, ops.router, events.router, content.router, comms.router,
          reviews.router, discover.router, site.router, admin.router):
    app.include_router(r)


@app.get("/whoami")
def whoami(request: Request):
    """The client IP as the API resolves it. Deploy check: `curl -H 'X-Forwarded-For: 1.2.3.4' https://yoursite/api/whoami`
    must NOT answer 1.2.3.4. If it does, TRUSTED_PROXIES or the front proxy is misconfigured."""
    return {"ip": client_ip(request)}


@app.get("/health")
def health():
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"ok": True}
