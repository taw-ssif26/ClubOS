"""Behaviour needed on free hosts: HTTPS email, provider caps, in-process worker, DB-stored images, trusted proxy secret."""
import io
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from starlette.requests import Request

from app import inproc_worker
from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import EmailOutbox
from app.net import client_ip
from app.services.mail import BrevoSender, process_outbox, queue_email
from tests.conftest import make_user

PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 80


class Rec:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body, unsubscribe_url=None):
        self.sent.append((to, subject))


def test_brevo_sender_speaks_the_http_api():
    seen = {}

    def handler(req: httpx.Request):
        seen.update(url=str(req.url), key=req.headers["api-key"], body=json.loads(req.content))
        return httpx.Response(201, json={"messageId": "<abc@smtp-relay.brevo.com>"})

    old = (settings.brevo_api_key, settings.smtp_from)
    settings.brevo_api_key, settings.smtp_from = "xkeysib-test-123", "ClubOS <no-reply@yourdomain.com>"
    try:
        BrevoSender(httpx.Client(transport=httpx.MockTransport(handler))).send("a@b.com", "Hi", "Body", "https://x/unsub")
        assert seen["url"] == "https://api.brevo.com/v3/smtp/email" and seen["key"] == "xkeysib-test-123"
        b = seen["body"]
        assert b["sender"] == {"email": "no-reply@yourdomain.com", "name": "ClubOS"} and b["to"] == [{"email": "a@b.com"}]
        assert b["subject"] == "Hi" and b["textContent"] == "Body" and b["headers"]["List-Unsubscribe"] == "<https://x/unsub>"
        bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, text="sender email is invalid")))
        with pytest.raises(RuntimeError, match="brevo 400"):
            BrevoSender(bad).send("a@b.com", "Hi", "Body")
        settings.smtp_from = "no-reply@yourdomain.com"            # bare address, no display name
        BrevoSender(httpx.Client(transport=httpx.MockTransport(handler))).send("a@b.com", "Hi", "Body")
        assert seen["body"]["sender"] == {"email": "no-reply@yourdomain.com"}
    finally:
        settings.brevo_api_key, settings.smtp_from = old


def test_sender_selection_prefers_brevo_then_smtp_then_console():
    from app.services.mail import ConsoleSender, SmtpSender, get_sender
    old = (settings.brevo_api_key, settings.smtp_host)
    try:
        settings.brevo_api_key, settings.smtp_host = "k", "smtp.example.com"
        assert isinstance(get_sender(), BrevoSender)
        settings.brevo_api_key = ""
        assert isinstance(get_sender(), SmtpSender)
        settings.smtp_host = ""
        assert isinstance(get_sender(), ConsoleSender)
    finally:
        settings.brevo_api_key, settings.smtp_host = old


def test_daily_cap_defers_and_transactional_mail_goes_first():
    with SessionLocal() as db:
        db.query(EmailOutbox).delete()
        for i in range(3):                                   # a campaign queued FIRST...
            queue_email(db, to=f"bulk{i}@x.com", subject="campaign", body="x").priority = 10
        queue_email(db, to="verify@x.com", subject="verify", body="x")   # ...then a verification email
        db.commit()
        old = settings.email_daily_cap
        settings.email_daily_cap = 2
        try:
            rec = Rec()
            assert process_outbox(db, rec) == (2, 0)
            assert rec.sent[0][1] == "verify"                # verification jumped the queue
            assert process_outbox(db, rec) == (0, 0)         # cap reached: the rest waits for tomorrow
            assert len(db.scalars(select(EmailOutbox).where(EmailOutbox.status == "pending")).all()) == 2
            settings.email_daily_cap = 0
            assert process_outbox(db, rec)[0] == 2
        finally:
            settings.email_daily_cap = old


def test_inprocess_worker_wakes_on_commit_not_on_rollback():
    inproc_worker.wake.clear()
    with SessionLocal() as db:
        queue_email(db, to="x@y.com", subject="s", body="b")
        db.rollback()
    assert not inproc_worker.wake.is_set()
    with SessionLocal() as db:
        queue_email(db, to="x@y.com", subject="s", body="b")
        db.commit()
    assert inproc_worker.wake.is_set()
    rec = Rec()
    assert inproc_worker.run_once(rec) >= 1 and rec.sent


def test_ping_never_touches_the_database():
    n = []
    def count(*a, **k):
        n.append(1)
    event.listen(engine, "before_cursor_execute", count)
    try:
        assert TestClient(app).get("/ping").json() == {"ok": True}
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert n == []


def test_proxy_secret_makes_forwarded_client_ip_trustworthy():
    def req(secret, ip, xff="6.6.6.6"):
        h = [(b"x-forwarded-for", xff.encode())]
        if secret is not None:
            h.append((b"x-proxy-secret", secret.encode()))
        if ip is not None:
            h.append((b"x-client-ip", ip.encode()))
        return Request({"type": "http", "headers": h, "client": ("10.0.0.9", 1), "method": "GET", "path": "/"})
    old = settings.proxy_secret
    settings.proxy_secret = "s" * 40
    try:
        assert client_ip(req("s" * 40, "203.0.113.7")) == "203.0.113.7"          # proxy proved itself
        assert client_ip(req("wrong" * 8, "203.0.113.7")) == "6.6.6.6"           # forged: ignored, falls back to the XFF chain (peer-appended entry)
        assert client_ip(req(None, "203.0.113.7")) == "6.6.6.6"
        assert client_ip(req("s" * 40, "not-an-ip")) == "6.6.6.6"                # garbage from the proxy never becomes the identity
        assert client_ip(req("s" * 40, "2001:db8::1")) == "2001:db8::1"
    finally:
        settings.proxy_secret = old


def test_images_can_live_in_postgres_for_hosts_without_disks():
    o = make_user("db_media")
    o.post("/clubs", json={"name": "Db Media", "slug": "db-media"})
    settings.media_backend = "db"
    try:
        r = o.post("/clubs/db-media/uploads", files={"file": ("l.png", io.BytesIO(PNG), "image/png")})
        assert r.status_code == 201, r.text
        url, uid = r.json()["url"], r.json()["id"]
        got = TestClient(app).get(url)
        assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"
        assert "immutable" in got.headers["cache-control"] and got.headers["x-content-type-options"] == "nosniff"
        assert o.get("/clubs/db-media/uploads").json()["used_bytes"] == len(PNG)          # still metered against the plan
        assert TestClient(app).get(url.replace(".png", ".jpg")).status_code == 404
        assert TestClient(app).get("/media/00000000-0000-0000-0000-000000000000/../x.png").status_code in (404, 422)
        assert o.delete(f"/clubs/db-media/uploads/{uid}").status_code == 200
        assert TestClient(app).get(url).status_code == 404
    finally:
        settings.media_backend = "disk"


def test_production_refuses_to_start_without_proxy_secret():
    old = (settings.cookie_secure, settings.secret_key, settings.proxy_secret)
    settings.cookie_secure, settings.secret_key, settings.proxy_secret = True, "k" * 40, "short"
    try:
        with pytest.raises(RuntimeError, match="PROXY_SECRET"):
            with TestClient(app):
                pass
    finally:
        settings.cookie_secure, settings.secret_key, settings.proxy_secret = old
