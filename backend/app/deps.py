"""Dépendances communes : session base, utilisateur courant, erreurs normalisées."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import firebase, security
from .accounts import is_valid_username, normalize_username, suggest_username
from .db import get_db
from .models import DEFAULT_PREFS, User

# Domaine technique des comptes créés par nom d'utilisateur dans Firebase Auth
# (Firebase exige un e-mail : « awa.kone » devient « awa.kone@users.autocut.invalid »).
PSEUDO_EMAIL_DOMAIN = "users.autocut.invalid"


def api_error(status: int, code: str, message: str, **extra) -> HTTPException:
    """Erreur au format {"detail": {"code", "message"}} : le message est affiché tel quel."""
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def _unauthorized():
    return api_error(401, "unauthorized", "Session expirée. Reconnectez-vous.")


def user_from_firebase(db: Session, claims: dict) -> User:
    """Retrouve (ou crée à la première connexion) le compte lié à l'utilisateur Firebase."""
    uid = claims["uid"]
    user = db.scalar(select(User).where(User.firebase_uid == uid))
    if user is not None:
        return user

    raw_email = (claims.get("email") or "").lower()
    pseudo = raw_email.endswith("@" + PSEUDO_EMAIL_DOMAIN)
    email = None if pseudo or not raw_email else raw_email
    verified = bool(claims.get("email_verified"))

    # Rattachement d'un compte existant uniquement par une adresse vérifiée (ex. Google).
    if email and verified:
        user = db.scalar(select(User).where(func.lower(User.email) == email, User.firebase_uid.is_(None)))
        if user is not None:
            user.firebase_uid = uid
            db.commit()
            return user

    def taken(candidate: str) -> bool:
        return db.scalar(select(User.id).where(User.username == candidate)) is not None

    wanted = normalize_username(raw_email.split("@")[0]) if pseudo else ""
    username = wanted if wanted and is_valid_username(wanted) and not taken(wanted) else suggest_username(
        claims.get("name") or raw_email or "user", taken
    )
    if email and db.scalar(select(User.id).where(func.lower(User.email) == email)):
        email = None  # adresse déjà utilisée par un autre compte non vérifié
    user = User(
        username=username,
        email=email,
        email_verified=verified,
        firebase_uid=uid,
        google_sub=None,
        name=(claims.get("name") or username)[:120],
        prefs=dict(DEFAULT_PREFS),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Deux premières requêtes simultanées : l'autre a créé le compte.
        db.rollback()
        user = db.scalar(select(User).where(User.firebase_uid == uid))
        if user is None:
            raise
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _bearer(request)
    if not token:
        raise _unauthorized()
    if firebase.looks_like_firebase_token(token):
        try:
            claims = firebase.verify_id_token(token)
        except firebase.FirebaseError as exc:
            raise _unauthorized() from exc
        return user_from_firebase(db, claims)
    payload = security.decode(token, "access")
    if payload is None:
        raise _unauthorized()
    user = db.get(User, payload.get("sub"))
    if user is None or payload.get("ver") != user.token_version:
        raise _unauthorized()
    return user
