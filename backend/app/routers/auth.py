"""Comptes : inscription par nom d'utilisateur (connexion immédiate), connexion par nom
d'utilisateur ou e-mail, connexion Google, mot de passe oublié."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import emails, security
from ..accounts import USERNAME_RULES, is_valid_username, normalize_username, suggest_username
from ..config import settings
from ..db import get_db
from ..deps import api_error
from ..models import DEFAULT_PREFS, User
from ..ratelimit import limit
from ..serializers import user_out

log = logging.getLogger("autocut.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    # Nom d'utilisateur ou adresse e-mail.
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(max_length=200)


class IdentifierIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=10, max_length=5000)


class ResetIn(BaseModel):
    token: str = Field(max_length=2000)
    password: str = Field(min_length=8, max_length=200)


def find_by_identifier(db: Session, identifier: str) -> User | None:
    value = identifier.strip().lower()
    return db.scalar(
        select(User).where(or_(User.username == value, func.lower(User.email) == value))
    )


def _username_taken(db: Session):
    return lambda candidate: db.scalar(select(User.id).where(User.username == candidate)) is not None


def _session(user: User, created: bool = False) -> dict:
    return {"access_token": security.access_token(user), "user": user_out(user), "created": created}


@router.get("/config")
def auth_config():
    """Ce dont l'écran de connexion a besoin (bouton Google affiché ou non)."""
    return {"google_client_id": settings.google_client_id or None}


@router.post("/register", status_code=201, dependencies=[Depends(limit("register", 10, 600))])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    username = normalize_username(body.username)
    if not is_valid_username(username):
        raise api_error(422, "bad_username", f"Nom d’utilisateur invalide. {USERNAME_RULES}")
    if _username_taken(db)(username):
        raise api_error(409, "username_taken", "Ce nom d’utilisateur est déjà pris. Choisissez-en un autre.")
    user = User(
        username=username,
        password_hash=security.hash_password(body.password),
        name=body.username.strip(),
        prefs=dict(DEFAULT_PREFS),
    )
    db.add(user)
    db.commit()
    # Connexion immédiate : aucune confirmation à faire.
    return _session(user, created=True)


@router.post("/login", dependencies=[Depends(limit("login", 10, 300))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = find_by_identifier(db, body.identifier)
    if user is None or not user.password_hash or not security.verify_password(body.password, user.password_hash):
        if user is not None and not user.password_hash and user.google_sub:
            raise api_error(401, "use_google", "Ce compte a été créé avec Google : utilisez « Continuer avec Google ».")
        raise api_error(401, "bad_credentials", "Nom d’utilisateur ou mot de passe incorrect.")
    return _session(user)


def _verify_google(credential: str) -> dict:
    if not settings.google_client_id:
        raise api_error(503, "google_disabled", "La connexion Google n’est pas encore configurée sur ce serveur.")
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        info = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_client_id)
    except Exception as exc:  # jeton expiré, mauvaise audience, signature invalide…
        log.warning("Jeton Google refusé : %s", exc)
        raise api_error(401, "google_invalid", "La connexion Google a échoué. Réessayez.") from exc
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise api_error(401, "google_invalid", "La connexion Google a échoué. Réessayez.")
    return info


@router.post("/google", dependencies=[Depends(limit("google", 20, 300))])
def google_login(body: GoogleIn, db: Session = Depends(get_db)):
    info = _verify_google(body.credential)
    sub = info["sub"]
    email = (info.get("email") or "").lower() if info.get("email_verified") else ""

    user = db.scalar(select(User).where(User.google_sub == sub))
    created = False
    if user is None and email:
        # Même adresse qu'un compte existant : on relie Google à ce compte.
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is not None:
            user.google_sub = sub
            user.email_verified = True
    if user is None:
        user = User(
            username=suggest_username(email or info.get("name") or "user", _username_taken(db)),
            email=email or None,
            email_verified=bool(email),
            google_sub=sub,
            name=(info.get("name") or (email.split("@")[0] if email else "")).strip()[:120],
            prefs=dict(DEFAULT_PREFS),
        )
        db.add(user)
        created = True
    db.commit()
    return _session(user, created=created)


@router.post("/forgot", dependencies=[Depends(limit("forgot", 5, 900))])
def forgot(body: IdentifierIn, db: Session = Depends(get_db)):
    user = find_by_identifier(db, body.identifier)
    if user and user.email:
        emails.send_reset(user.email, security.reset_token(user))
    # Réponse identique dans tous les cas : on ne révèle pas quels comptes existent.
    return {
        "message": "Si un e-mail est associé à ce compte, un lien de réinitialisation vient d’être envoyé."
    }


@router.post("/reset", dependencies=[Depends(limit("reset", 10, 900))])
def reset(body: ResetIn, db: Session = Depends(get_db)):
    payload = security.decode(body.token, "reset")
    user = db.get(User, payload["sub"]) if payload else None
    if user is None or not security.reset_token_valid(payload, user):
        raise api_error(400, "invalid_token", "Ce lien de réinitialisation est invalide ou a expiré.")
    user.password_hash = security.hash_password(body.password)
    user.token_version += 1  # déconnecte les autres sessions
    db.commit()
    return _session(user)
