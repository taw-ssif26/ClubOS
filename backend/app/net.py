import hmac
import ipaddress

from fastapi import Request

from .config import settings


def client_ip(request: Request) -> str:
    """Real client IP that a visitor cannot spoof.

    Every trusted proxy appends the address of ITS peer to X-Forwarded-For, so with N trusted hops the
    entry at position -N is the first address a trusted proxy actually saw. Anything to its left is
    client-supplied and ignored. The API port must NOT be reachable from the internet, otherwise the
    attacker is the 'proxy'.
    """
    secret = settings.proxy_secret
    if secret and hmac.compare_digest(request.headers.get("x-proxy-secret", "").encode(), secret.encode()):
        # The web proxy proved who it is, so the IP it forwards is the one IT resolved from its trusted edge.
        try:
            return str(ipaddress.ip_address(request.headers.get("x-client-ip", "").strip()))
        except ValueError:
            pass
    n = settings.trusted_proxies
    peer = request.client.host if request.client else "unknown"
    if n <= 0:
        return peer
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return parts[-n] if len(parts) >= n else (parts[0] if parts else peer)
