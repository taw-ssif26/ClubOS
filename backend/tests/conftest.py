import os
import re

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_clubos.db")
os.environ.setdefault("CLUB_APPROVAL_REQUIRED", "false")  # most tests are about club behaviour; approval has its own tests
os.environ["RATE_LIMIT_ENABLED"] = "false"
if os.path.exists("test_clubos.db"):
    os.remove("test_clubos.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import EmailOutbox

PASSWORD = "correct-horse-battery"


def make_user(name: str, verified: bool = True) -> TestClient:
    c = TestClient(app)
    with c:
        pass
    r = c.post("/auth/register", json={"email": f"{name}@ndc.edu.bd", "username": name, "password": PASSWORD, "full_name": f"{name.title()} Person", "accept_terms": True})
    assert r.status_code == 201, r.text
    if verified:
        verify(c, f"{name}@ndc.edu.bd")
    r = c.post("/auth/login", json={"email": f"{name}@ndc.edu.bd", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return c


def last_mail(to: str) -> str:
    with SessionLocal() as db:
        row = db.scalars(select(EmailOutbox).where(EmailOutbox.to_email == to).order_by(EmailOutbox.created_at.desc())).first()
        return row.body if row else ""


def verify(c: TestClient, email: str):
    body = last_mail(email)
    token = re.search(r"token=([\w-]+)", body).group(1)
    assert c.post("/auth/verify-email", json={"token": token}).status_code == 200


@pytest.fixture(scope="session", autouse=True)
def _boot():
    from app.db import Base, engine
    Base.metadata.drop_all(engine)
    with TestClient(app):  # triggers lifespan -> create_all
        yield


def db_set_plan(slug: str, plan: str):
    from app.models import Club
    with SessionLocal() as db:
        c = db.scalars(select(Club).where(Club.slug == slug)).one()
        c.plan, c.plan_expires_at = plan, None
        db.commit()


def make_admin(c: TestClient, username: str):
    from app.models import User
    with SessionLocal() as db:
        u = db.scalars(select(User).where(User.username == username)).one()
        u.is_platform_admin, u.totp_enabled = True, True  # admin area requires 2FA; flows that need the real enrolment are in test_hardening
        db.commit()
