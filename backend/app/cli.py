"""python -m app.cli make-admin you@example.com"""
import sys

from sqlalchemy import select

from .db import SessionLocal
from .models import User


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("migrate", "db-status"):
        from . import dbtools
        sys.exit(dbtools.migrate() if sys.argv[1] == "migrate" else dbtools.status())
    if len(sys.argv) != 3 or sys.argv[1] not in ("make-admin", "reset-2fa"):
        sys.exit("usage: python -m app.cli migrate | db-status | make-admin <email> | reset-2fa <email>")
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == sys.argv[2].lower()))
        if not u:
            sys.exit("no such user")
        if sys.argv[1] == "make-admin":
            u.is_platform_admin = True
            print(f"{u.email} is now a platform admin (they must enable 2FA before using /admin)")
        else:
            u.totp_enabled, u.totp_secret = False, None  # lost-device recovery; requires server access
            print(f"2FA reset for {u.email}")
        db.commit()


if __name__ == "__main__":
    main()
