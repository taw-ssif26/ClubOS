"""Email worker that runs INSIDE the API process (for hosts with no background workers, e.g. Render free).

Designed so a scale-to-zero database (Neon) can sleep: it does NOT poll every few seconds. It wakes
(a) immediately after any request commits a queued email, and (b) on a slow timer for scheduled sends and retries."""
import logging
import threading
import time

from sqlalchemy import event
from sqlalchemy.orm import Session as SASession

from .config import settings
from .db import SessionLocal
from .models import EmailOutbox
from .services.maintenance import purge
from .services.mail import get_sender, process_outbox

log = logging.getLogger("clubos.worker")
wake = threading.Event()
stop = threading.Event()


@event.listens_for(SASession, "after_flush")
def _mark(session, _ctx):
    if any(isinstance(o, EmailOutbox) for o in session.new):
        session.info["email_queued"] = True


@event.listens_for(SASession, "after_commit")
def _wake(session):
    if session.info.pop("email_queued", False):
        wake.set()


@event.listens_for(SASession, "after_rollback")
def _clear(session):
    session.info.pop("email_queued", None)


def run_once(sender=None) -> int:
    sender = sender or get_sender()
    total = 0
    with SessionLocal() as db:
        while True:
            sent, failed = process_outbox(db, sender)
            total += sent
            if not (sent or failed):
                return total


def _loop():
    sender, last_purge = get_sender(), 0.0
    log.info("in-process email worker started (%s, poll %ss)", type(sender).__name__, settings.worker_poll_seconds)
    while not stop.is_set():
        try:
            n = run_once(sender)
            if n:
                log.info("emails sent=%s", n)
            if time.time() - last_purge > 86400:
                with SessionLocal() as db:
                    log.info("retention purge: %s", purge(db))
                last_purge = time.time()
        except Exception:  # noqa: BLE001 - never let the thread die
            log.exception("worker iteration failed")
        wake.wait(settings.worker_poll_seconds)
        wake.clear()


def start() -> threading.Thread:
    t = threading.Thread(target=_loop, name="email-worker", daemon=True)
    t.start()
    return t
