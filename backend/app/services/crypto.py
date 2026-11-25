import base64
import hashlib
import hmac
import time

import pyotp
from cryptography.fernet import Fernet

from ..config import settings


def _key() -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256((settings.secret_key or "dev-only-insecure-key").encode()).digest())


def encrypt(s: str) -> str:
    return Fernet(_key()).encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    return Fernet(_key()).decrypt(s.encode()).decode()


def sign(*parts: str) -> str:
    mac = hmac.new((settings.secret_key or "dev-only-insecure-key").encode(), ":".join(parts).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac)[:32].decode()


def check_sig(sig: str, *parts: str) -> bool:
    return hmac.compare_digest(sig, sign(*parts))


def verify_totp(user, code: str) -> bool:
    """RFC 6238 with +-1 step tolerance and replay protection (a code works once)."""
    if not user.totp_secret or not code or not code.isdigit():
        return False
    totp = pyotp.TOTP(decrypt(user.totp_secret))
    now = int(time.time())
    for offset in (-1, 0, 1):
        step = now // 30 + offset
        if hmac.compare_digest(totp.at(step * 30), code) and step > (user.totp_last_step or 0):
            user.totp_last_step = step
            return True
    return False
