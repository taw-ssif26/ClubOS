import re
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import EmailOptOut, EmailOutbox, EmailToken, LoginEvent, Session as UserSession, User
from app.net import client_ip
from app.ratelimit import hit
from app.services.mail import process_outbox
from app.services.maintenance import purge
from tests.conftest import PASSWORD, db_set_plan, last_mail, make_admin, make_user, verify

FUT = lambda d: (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()  # noqa: E731


def _req(xff: str | None, peer="10.0.0.5") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234), "method": "GET", "path": "/"})


def test_client_ip_cannot_be_spoofed():
    old = settings.trusted_proxies
    try:
        settings.trusted_proxies = 1   # web proxy appends the address it saw: [client-supplied..., real client]
        assert client_ip(_req("6.6.6.6, 203.0.113.9")) == "203.0.113.9"          # attacker-supplied left entry ignored
        assert client_ip(_req("6.6.6.6, 7.7.7.7, 203.0.113.9")) == "203.0.113.9"
        assert client_ip(_req(None)) == "10.0.0.5"                               # no header: fall back to the peer
        settings.trusted_proxies = 2   # edge proxy + web proxy
        assert client_ip(_req("6.6.6.6, 203.0.113.9, 10.1.1.1")) == "203.0.113.9"
        settings.trusted_proxies = 0
        assert client_ip(_req("6.6.6.6")) == "10.0.0.5"
    finally:
        settings.trusted_proxies = old


def test_rate_limiter_blocks_and_recovers():
    assert all(hit("t-key", 3, 60) for _ in range(3)) and not hit("t-key", 3, 60)
    assert hit("other-key", 3, 60)


def test_register_requires_terms_and_login_never_returns_token():
    c = TestClient(app)
    base = {"email": "terms@ndc.edu.bd", "username": "terms_u", "password": PASSWORD, "full_name": "Terms U"}
    assert c.post("/auth/register", json=base).status_code == 422
    assert c.post("/auth/register", json={**base, "accept_terms": False}).status_code == 422
    assert c.post("/auth/register", json={**base, "accept_terms": True}).status_code == 201
    with SessionLocal() as db:
        u = db.scalars(select(User).where(User.username == "terms_u")).one()
        assert u.terms_accepted_at and u.terms_version == settings.terms_version
    r = c.post("/auth/login", json={"email": base["email"], "password": PASSWORD})
    assert r.status_code == 200 and "token" not in r.json() and "clubos_session" in r.headers["set-cookie"] and "httponly" in r.headers["set-cookie"].lower()


def test_resend_verification_and_password_change():
    c = make_user("resend_u", verified=False)
    assert c.post("/auth/resend-verification").status_code == 429                  # one was just sent at registration
    with SessionLocal() as db:
        for t in db.scalars(select(EmailToken)).all():
            t.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()
    assert c.post("/auth/resend-verification").status_code == 200
    verify(c, "resend_u@ndc.edu.bd")                                                # the NEW link works
    assert c.get("/users/me").json()["email_verified"] is True
    # password change signs out other devices, keeps this one
    other = TestClient(app)
    other.post("/auth/login", json={"email": "resend_u@ndc.edu.bd", "password": PASSWORD})
    assert other.get("/users/me").status_code == 200
    assert c.post("/auth/change-password", json={"current_password": "wrong-password-x", "new_password": "a-different-password"}).status_code == 403
    assert c.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "a-different-password"}).status_code == 200
    assert other.get("/users/me").status_code == 401 and c.get("/users/me").status_code == 200


def test_two_factor_flow_and_admin_requirement():
    c = make_user("tfa_u")
    secret = c.post("/auth/2fa/setup").json()["secret"]
    assert c.get("/auth/2fa/qr.svg").headers["content-type"] == "image/svg+xml"
    totp = pyotp.TOTP(secret)
    assert c.post("/auth/2fa/enable", json={"code": "000000"}).status_code == 422
    assert c.post("/auth/2fa/enable", json={"code": totp.now()}).status_code == 200
    with SessionLocal() as db:   # secret is encrypted at rest
        assert secret not in db.scalars(select(User).where(User.username == "tfa_u")).one().totp_secret
    login = lambda code=None: TestClient(app).post("/auth/login", json={"email": "tfa_u@ndc.edu.bd", "password": PASSWORD, **({"code": code} if code else {})})  # noqa: E731
    r = login()
    assert r.status_code == 401 and r.json()["detail"]["code"] == "totp_required"
    assert login("123456").status_code == 401
    nxt = totp.at(datetime.now(timezone.utc) + timedelta(seconds=30))             # the code used to enable can't be replayed
    assert login(totp.now()).status_code == 401
    assert login(nxt).status_code == 200
    assert login(nxt).status_code == 401                                           # ...and a code works exactly once
    # admins can't use /admin without 2FA
    adm = make_user("tfa_admin")
    with SessionLocal() as db:
        db.scalars(select(User).where(User.username == "tfa_admin")).one().is_platform_admin = True
        db.commit()
    assert adm.get("/admin/stats").json()["detail"]["code"] == "admin_2fa_required"
    s2 = adm.post("/auth/2fa/setup").json()["secret"]
    assert adm.post("/auth/2fa/enable", json={"code": pyotp.TOTP(s2).now()}).status_code == 200
    assert adm.get("/admin/stats").status_code == 200
    assert c.post("/auth/2fa/disable", json={"password": "nope-nope-nope", "code": "123456"}).status_code == 403


def test_unsubscribe_is_honoured():
    o, a, b = make_user("un_owner"), make_user("un_a"), make_user("un_b")
    o.post("/clubs", json={"name": "Unsub Club", "slug": "unsub-club", "join_policy": "open"})
    db_set_plan("unsub-club", "pro")
    for u in (a, b):
        u.post("/clubs/unsub-club/join", json={})
    send = lambda: o.post("/clubs/unsub-club/communications", json={"subject": "News", "body": "Hi {{first_name}}", "audience": {"type": "all_members"}})  # noqa: E731
    assert send().json()["queued"] == 3
    body = last_mail("un_a@ndc.edu.bd")
    link = re.search(r"unsubscribe\?u=([\w-]+)&c=([\w-]+)&t=([\w-]+)", body)
    assert link and "Unsubscribe from Unsub Club" in body
    u, c, t = link.groups()
    anon = TestClient(app)
    assert anon.post("/unsubscribe", json={"u": u, "c": c, "t": "x" * 32}).status_code == 400   # forged signature
    assert anon.post("/unsubscribe", json={"u": u, "c": c, "t": t}).status_code == 200
    assert anon.post("/unsubscribe", json={"u": u, "c": c, "t": t}).status_code == 200           # idempotent
    r = send().json()
    assert r["queued"] == 2 and r["skipped_unsubscribed"] == 1
    with SessionLocal() as db:
        row = db.scalars(select(EmailOutbox).where(EmailOutbox.to_email == "un_b@ndc.edu.bd", EmailOutbox.subject == "News")).first()
        assert row.unsubscribe_url.startswith(settings.base_url + "/unsubscribe")


def test_delete_account_and_export():
    o, m = make_user("del_owner"), make_user("del_member")
    o.post("/clubs", json={"name": "Del Club", "slug": "del-club", "join_policy": "open"})
    m.post("/clubs/del-club/join", json={})
    m.put("/clubs/del-club/reviews/mine", json={"rating": 5, "body": "great club for beginners and experts alike"})
    exp = m.get("/users/me/export")
    assert exp.status_code == 200 and exp.json()["profile"]["email"] == "del_member@ndc.edu.bd" and len(exp.json()["reviews"]) == 1
    # sole owner can't vanish
    r = o.request("DELETE", "/users/me", json={"password": PASSWORD})
    assert r.status_code == 409 and "Del Club" in r.json()["detail"]
    assert m.request("DELETE", "/users/me", json={"password": "wrong-password-x"}).status_code == 403
    assert m.request("DELETE", "/users/me", json={"password": PASSWORD}).status_code == 200
    assert m.get("/users/me").status_code == 401
    assert TestClient(app).post("/auth/login", json={"email": "del_member@ndc.edu.bd", "password": PASSWORD}).status_code == 401
    with SessionLocal() as db:
        u = db.scalars(select(User).where(User.username.like("deleted_%"))).first()
        assert u and u.full_name == "Deleted user" and "ndc.edu.bd" not in u.email and not u.is_active
    assert TestClient(app).get("/clubs/del-club/reviews").json()["summary"]["count"] == 0


def test_privacy_defaults_and_review_names():
    o, m = make_user("pv_owner"), make_user("pv_member")
    o.post("/clubs", json={"name": "Priv Club", "slug": "priv-club", "join_policy": "open"})
    m.post("/clubs/priv-club/join", json={})
    m.put("/clubs/priv-club/reviews/mine", json={"rating": 4, "body": "solid"})
    item = TestClient(app).get("/clubs/priv-club/reviews").json()["items"][0]
    assert item["user"] == {"full_name": "Pv_Member P."}     # first name + last initial only; no username, no avatar
    assert TestClient(app).get("/users/pv_member").status_code == 404


def test_css_and_url_injection_rejected():
    o = make_user("inj_owner")
    o.post("/clubs", json={"name": "Inj Club", "slug": "inj-club"})
    for bad in ('https://x.com/a.png);background:url(//evil', 'https://x.com/a b.png', 'javascript:alert(1)', "/media/../../etc/passwd", 'https://x.com/"onerror="x'):
        assert o.patch("/clubs/inj-club", json={"cover_url": bad}).status_code == 422, bad
    assert o.patch("/clubs/inj-club", json={"cover_url": "/media/abc/def.png"}).status_code == 200
    assert o.patch("/clubs/inj-club", json={"cover_url": "https://cdn.example.com/cover.jpg"}).status_code == 200


def test_headers_request_id_and_retention():
    r = TestClient(app).get("/health")
    assert r.headers["x-request-id"] and r.headers["x-frame-options"] == "DENY"
    assert TestClient(app).get("/health", headers={"x-request-id": "abc123"}).headers["x-request-id"] == "abc123"
    u = make_user("ret_u")
    with SessionLocal() as db:
        old = datetime.now(timezone.utc) - timedelta(days=120)
        db.add(LoginEvent(email="old@x.com", success=False, created_at=old))
        for s in db.scalars(select(UserSession)).all()[:1]:
            s.expires_at = datetime.now(timezone.utc) - timedelta(days=30)
        db.commit()
        out = purge(db)
        assert out["login_events"] >= 1 and out["sessions"] >= 1


def test_signed_in_limits_are_per_session_not_per_ip():
    """Two students on the same campus Wi-Fi must not share a rate-limit budget."""
    from app.ratelimit import limit_key
    def req(cookie):
        h = [(b"cookie", f"clubos_session={cookie}".encode())] if cookie else []
        h.append((b"x-forwarded-for", b"203.0.113.50"))
        return Request({"type": "http", "headers": h, "client": ("10.0.0.5", 1), "method": "POST", "path": "/"})
    a, b = limit_key(req("A" * 40)), limit_key(req("B" * 40))
    assert a != b and a.startswith("s:")
    assert limit_key(req(None)) == "ip:203.0.113.50"


def test_whoami_reports_resolved_ip():
    r = TestClient(app).get("/whoami", headers={"x-forwarded-for": "6.6.6.6, 203.0.113.9"})
    assert r.status_code == 200 and r.json()["ip"] == "203.0.113.9"   # TRUSTED_PROXIES=1 default
