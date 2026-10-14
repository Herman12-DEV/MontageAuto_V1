"""Hachage des mots de passe (bcrypt) et jetons signés (JWT HS256)."""

from __future__ import annotations

import hashlib
import time
from datetime import timedelta

import bcrypt
import jwt

from .config import settings
from .models import User

ACCESS_TTL = timedelta(days=7)
RESET_TTL = timedelta(hours=1)
MEDIA_TTL = timedelta(hours=6)


def hash_password(password: str) -> str:
    # bcrypt ne lit que 72 octets : on pré-hache pour accepter les mots de passe longs.
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")
    return bcrypt.hashpw(digest, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")
    try:
        return bcrypt.checkpw(digest, hashed.encode("ascii"))
    except ValueError:
        return False


def _encode(payload: dict, ttl: timedelta) -> str:
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + int(ttl.total_seconds())}
    return jwt.encode(body, settings.secret_key, algorithm="HS256")


def decode(token: str, typ: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_iat": False},
            leeway=5,
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != typ:
        return None
    return payload


def _fingerprint(user: User) -> str:
    # Lié au hash actuel : le lien de réinitialisation devient inutilisable une fois servi.
    return hashlib.sha256(f"{user.password_hash}:{user.token_version}".encode()).hexdigest()[:16]


def access_token(user: User) -> str:
    return _encode({"typ": "access", "sub": user.id, "ver": user.token_version}, ACCESS_TTL)


def reset_token(user: User) -> str:
    return _encode({"typ": "reset", "sub": user.id, "fp": _fingerprint(user)}, RESET_TTL)


def reset_token_valid(payload: dict, user: User) -> bool:
    return payload.get("fp") == _fingerprint(user)


def media_token(user: User, project_id: str) -> str:
    """Jeton court pour les balises <video>/<a> qui ne peuvent pas envoyer d'en-tête."""
    return _encode({"typ": "media", "sub": user.id, "pid": project_id}, MEDIA_TTL)
