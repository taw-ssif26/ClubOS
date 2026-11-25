import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text,
                        UniqueConstraint, Uuid, false, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; Postgres returns aware. Normalize."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def created():
    return mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(160), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    class_year: Mapped[str | None] = mapped_column(String(40), nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    profile_public: Mapped[bool] = mapped_column(Boolean, default=False)  # private by default
    show_email: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    place: Mapped[str | None] = mapped_column(String(40), nullable=True)            # private: only used to rank "near me"
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)           # rounded to ~1 km before saving
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(300), nullable=True)   # Fernet-encrypted
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_last_step: Mapped[int] = mapped_column(Integer, default=0)
    created_at = created()


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at = created()


class EmailToken(Base):
    __tablename__ = "email_tokens"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # verify | reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at = created()


class LoginEvent(Base):
    __tablename__ = "login_events"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    success: Mapped[bool] = mapped_column(Boolean)
    created_at = created()


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # Users with a *verified* email on this domain count as institution members.
    email_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at = created()


class Club(Base):
    __tablename__ = "clubs"
    id: Mapped[uuid.UUID] = pk()
    institution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institutions.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="general", index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    visibility: Mapped[str] = mapped_column(String(20), default="public")   # public|private|institution|unlisted
    join_policy: Mapped[str] = mapped_column(String(20), default="request")  # open|request|invite
    application_fields: Mapped[list] = mapped_column(JSON, default=list)
    theme: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[str] = mapped_column(String(30), default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Anti-spam: new clubs wait for super-admin approval. Existing clubs migrate as "approved" (server_default).
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default=text("'approved'"), index=True)  # pending|approved|rejected
    status_note: Mapped[str | None] = mapped_column(String(500), nullable=True)      # reviewer's reason when rejected
    leaderboard_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    location_mode: Mapped[str] = mapped_column(String(10), default="onsite", server_default=text("'onsite'"))  # onsite | online | hybrid
    place: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)   # id from services/places.py
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at = created()
    institution: Mapped["Institution | None"] = relationship(lazy="joined")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    rank: Mapped[int] = mapped_column(Integer, default=10)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("club_id", "name"),)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    application: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = created()
    role: Mapped["Role"] = relationship(lazy="joined")
    user: Mapped["User"] = relationship(lazy="joined")
    club: Mapped["Club"] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("club_id", "user_id"), Index("ix_membership_club_status", "club_id", "status"))


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="announcement")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|published
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)  # [{id,url,name,size,kind,content_type}]
    created_at = created()


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    venue: Mapped[str] = mapped_column(String(200), default="")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    online_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="public")  # public|members|private
    status: Mapped[str] = mapped_column(String(20), default="draft")       # draft|published|cancelled
    registration_fields: Mapped[list] = mapped_column(JSON, default=list)
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location_mode: Mapped[str] = mapped_column(String(10), default="onsite", server_default=text("'onsite'"))  # onsite | online | hybrid
    place: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)   # id from services/places.py
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at = created()
    club: Mapped["Club"] = relationship(lazy="joined")


class Registration(Base):
    __tablename__ = "registrations"
    id: Mapped[uuid.UUID] = pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # confirmed|waitlisted|cancelled
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    ticket_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at = created()
    user: Mapped["User"] = relationship(lazy="joined")
    event: Mapped["Event"] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)


class Form(Base):
    __tablename__ = "forms"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    fields: Mapped[list] = mapped_column(JSON, default=list)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_submissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at = created()


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[uuid.UUID] = pk()
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at = created()
    user: Mapped["User"] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("form_id", "user_id"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = created()


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    to_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|sent|failed
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at = created()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unsubscribe_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)   # 0 = transactional (verification, confirmations); 10 = bulk campaigns


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at = created()


class Plan(Base):
    """Editable from the super admin. Limits: None = unlimited. Flags: bool."""
    __tablename__ = "plans"
    id: Mapped[uuid.UUID] = pk()
    key: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    tagline: Mapped[str] = mapped_column(String(200), default="")
    price_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)  # BDT; None = "contact us"
    price_label: Mapped[str] = mapped_column(String(80), default="")
    cta_label: Mapped[str] = mapped_column(String(60), default="Choose plan")
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    features: Mapped[list] = mapped_column(JSON, default=list)   # [{label, status: live|soon, group}]
    highlighted: Mapped[bool] = mapped_column(Boolean, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class SiteContent(Base):
    __tablename__ = "site_content"
    id: Mapped[uuid.UUID] = pk()
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[uuid.UUID] = pk()
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(400), default="")
    badge: Mapped[str] = mapped_column(String(40), default="")
    cta_label: Mapped[str] = mapped_column(String(60), default="")
    cta_url: Mapped[str] = mapped_column(String(300), default="")
    plan_key: Mapped[str | None] = mapped_column(String(30), nullable=True)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    placement: Mapped[str] = mapped_column(String(20), default="banner")  # banner | pricing | both
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at = created()


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[uuid.UUID] = pk()
    target_key: Mapped[str] = mapped_column(String(80))          # club:<id> | event:<id>
    target_type: Mapped[str] = mapped_column(String(10), index=True)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="published", index=True)  # published | hidden
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reporters: Mapped[list] = mapped_column(JSON, default=list)
    created_at = created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    user: Mapped["User"] = relationship(lazy="joined")
    club: Mapped["Club"] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("user_id", "target_key"), Index("ix_reviews_target", "target_key", "status"))


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    stored_name: Mapped[str] = mapped_column(String(80))
    original_name: Mapped[str] = mapped_column(String(200), default="")
    content_type: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(10), default="image", server_default=text("'image'"))  # image | document
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)  # only when MEDIA_BACKEND=db
    created_at = created()


class UpgradeRequest(Base):
    """Manual billing: club asks, you collect payment (bKash/bank), then approve in super admin."""
    __tablename__ = "upgrade_requests"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    plan_key: Mapped[str] = mapped_column(String(30))
    months: Mapped[int] = mapped_column(Integer, default=1)
    contact: Mapped[str] = mapped_column(String(120), default="")
    message: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending|approved|rejected
    created_at = created()
    club: Mapped["Club"] = relationship(lazy="joined")
    user: Mapped["User"] = relationship(lazy="joined")


class EmailOptOut(Base):
    __tablename__ = "email_optouts"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    created_at = created()
    __table_args__ = (UniqueConstraint("user_id", "club_id"),)


class PointEntry(Base):
    """Append-only points ledger for a club's leaderboard. Visible only inside the club."""
    __tablename__ = "point_entries"
    id: Mapped[uuid.UUID] = pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    points: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    awarded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at = created()
    recipient: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="joined")
    awarder: Mapped["User"] = relationship(foreign_keys=[awarded_by], lazy="joined")
    __table_args__ = (Index("ix_points_club_user", "club_id", "user_id"),)
