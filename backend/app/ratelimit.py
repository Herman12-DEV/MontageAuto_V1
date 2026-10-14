"""Limitation de débit en mémoire par adresse IP (NF-SEC-03).

Suffisant pour un processus d'API unique (V1). Avec plusieurs instances d'API derrière
un répartiteur, déplacer ces compteurs dans Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and settings.is_production:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "inconnu"


def limit(bucket: str, max_hits: int, window_s: int):
    """Dépendance FastAPI : `Depends(limit("login", 10, 60))`."""

    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        key = (bucket, client_ip(request))
        now = time.monotonic()
        with _lock:
            hits = _hits[key]
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= max_hits:
                retry = int(window_s - (now - hits[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "rate_limited",
                        "message": f"Trop de tentatives. Réessayez dans {retry} s.",
                    },
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    return dependency


def reset() -> None:
    with _lock:
        _hits.clear()
