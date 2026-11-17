"""Email worker + retention. Run as its own process: python -m app.worker"""
import logging
import time

from .config import settings
from .db import SessionLocal
from .services.maintenance import purge
from .services.mail import get_sender, process_outbox

log = logging.getLogger("clubos.worker")


def main(interval: int = 10):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, send_default_pii=False)
    sender = get_sender()
    log.info("worker started with %s", type(sender).__name__)
    last_purge = 0.0
    while True:
        try:
            with SessionLocal() as db:
                sent, failed = process_outbox(db, sender)
                if sent or failed:
                    log.info("emails sent=%s failed=%s", sent, failed)
                if time.time() - last_purge > 3600:
                    log.info("retention purge: %s", purge(db))
                    last_purge = time.time()
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("worker iteration failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
