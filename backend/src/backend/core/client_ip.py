"""Who is calling, for the few routes that work without signing in."""

import hashlib

from fastapi import Request


def client_ip(request: Request) -> str:
    """The visitor's address, used only to rate limit them.

    Behind the host's proxy the socket address is the proxy's. The proxy passes
    the real one in X-Real-IP, or as the last entry of X-Forwarded-For (earlier
    entries are whatever the caller chose to send).
    """
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def hash_ip(ip: str) -> str:
    """What is stored in place of the address, which is never kept itself."""
    return hashlib.sha256(ip.encode()).hexdigest()
