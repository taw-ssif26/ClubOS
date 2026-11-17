from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import COOKIE, current_user
from ..models import EmailToken, LoginEvent, Session as UserSession, User, aware, utcnow
from ..net import client_ip
from ..ratelimit import rate_limit
from ..services.crypto import verify_totp
from ..security import DUMMY_HASH, hash_password, new_token, token_hash, verify_password
from ..services.core import notify
from ..services.mail import queue_email
from .users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])
MAX_FAILS, FAIL_WINDOW = 5, timedelta(minutes=15)


class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(pattern=r"^[a-z0-9_]{3,30}$")
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    accept_terms: bool

    @field_validator("email")
    @classmethod
    def lower(cls, v):
        return v.lower()

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, v):
        if v is not True:
            raise ValueError("You must accept the Terms and Privacy Policy")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    code: str | None = Field(None, max_length=8)

    @field_validator("email")
    @classmethod
    def lower(cls, v):
        return v.lower()


class TokenIn(BaseModel):
    token: str


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=128)


def _issue_email_token(db: Session, user: User, kind: str, hours: int) -> str:
    raw = new_token()
    db.add(EmailToken(user_id=user.id, kind=kind, token_hash=token_hash(raw), expires_at=utcnow() + timedelta(hours=hours)))
    return raw


def _consume(db: Session, raw: str, kind: str) -> User:
    t = db.scalar(select(EmailToken).where(EmailToken.token_hash == token_hash(raw), EmailToken.kind == kind))
    if not t or t.used or aware(t.expires_at) < utcnow():
        raise HTTPException(400, "Invalid or expired token")
    t.used = True
    return db.get(User, t.user_id)


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit("register", 100, 3600, per="ip"))])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Email already registered")
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(409, "Username taken")
    user = User(email=body.email, username=body.username, full_name=body.full_name.strip(),
                password_hash=hash_password(body.password), terms_accepted_at=utcnow(), terms_version=settings.terms_version)
    db.add(user)
    db.flush()
    raw = _issue_email_token(db, user, "verify", 48)
    queue_email(db, to=user.email, subject="Verify your ClubOS email",
                body=f"Hi {user.full_name.split()[0]},\n\nConfirm your email:\n{settings.base_url}/verify-email?token={raw}\n")
    db.commit()
    return user_out(user, private=True)


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    user = _consume(db, body.token, "verify")
    user.email_verified = True
    db.commit()
    return {"ok": True}


@router.post("/login", dependencies=[Depends(rate_limit("login", 60, 60, per="ip"))])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")[:300]
    fails = db.scalar(select(func.count()).select_from(LoginEvent).where(
        LoginEvent.email == body.email, LoginEvent.success.is_(False), LoginEvent.created_at >= utcnow() - FAIL_WINDOW))
    if fails >= MAX_FAILS:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == body.email))
    # always run a hash verification so response time doesn't reveal whether the email exists
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password) and user is not None and user.is_active
    if ok and user.totp_enabled:
        if not body.code:
            raise HTTPException(401, {"code": "totp_required", "message": "Enter the 6-digit code from your authenticator app"})
        ok = verify_totp(user, body.code.strip())  # wrong or replayed codes count as failed logins
    db.add(LoginEvent(user_id=user.id if user else None, email=body.email, ip=ip, user_agent=ua, success=ok))
    if not ok:
        db.commit()
        raise HTTPException(401, "Invalid email, password or code")
    seen_ip = db.scalar(select(LoginEvent.id).where(LoginEvent.user_id == user.id, LoginEvent.success.is_(True), LoginEvent.ip == ip))
    if not seen_ip and db.scalar(select(LoginEvent.id).where(LoginEvent.user_id == user.id, LoginEvent.success.is_(True))):
        notify(db, user.id, "New sign-in from an unfamiliar network", f"IP {ip}. If this wasn't you, change your password and revoke sessions.")
    raw = new_token()
    db.add(UserSession(user_id=user.id, token_hash=token_hash(raw), user_agent=ua, ip=ip,
                       expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours)))
    db.commit()
    # The session token lives ONLY in the HttpOnly cookie: page JavaScript (and any XSS) can never read it.
    response.set_cookie(COOKIE, raw, httponly=True, samesite="lax", secure=settings.cookie_secure,
                        max_age=settings.session_ttl_hours * 3600, path="/")
    return {"user": user_out(user, private=True)}


@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(UserSession, request.state.session_id)
    if s:
        s.revoked = True
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/sessions")
def sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked.is_(False))
                      .order_by(UserSession.created_at.desc())).all()
    return [{"id": str(s.id), "user_agent": s.user_agent, "ip": s.ip, "created_at": aware(s.created_at).isoformat(),
             "current": s.id == request.state.session_id} for s in rows if aware(s.expires_at) > utcnow()]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id))
    if not s:
        raise HTTPException(404, "Session not found")
    s.revoked = True
    db.commit()
    return {"ok": True}


@router.get("/login-history")
def login_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(LoginEvent).where(LoginEvent.user_id == user.id).order_by(LoginEvent.created_at.desc()).limit(50)).all()
    return [{"ip": r.ip, "user_agent": r.user_agent, "success": r.success, "at": aware(r.created_at).isoformat()} for r in rows]


@router.post("/password-reset/request", dependencies=[Depends(rate_limit("reset", 30, 3600, per="ip"))])
def reset_request(body: ResetRequestIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.is_active:
        raw = _issue_email_token(db, user, "reset", 1)
        queue_email(db, to=user.email, subject="Reset your ClubOS password",
                    body=f"Reset your password (valid 1 hour):\n{settings.base_url}/reset-password?token={raw}\n\nIgnore this if it wasn't you.")
        db.commit()
    return {"ok": True}  # identical response whether or not the account exists


@router.post("/password-reset/confirm")
def reset_confirm(body: ResetConfirmIn, db: Session = Depends(get_db)):
    user = _consume(db, body.token, "reset")
    user.password_hash = hash_password(body.password)
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked.is_(False))):
        s.revoked = True
    db.commit()
    return {"ok": True}
