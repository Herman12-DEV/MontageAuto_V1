"""Profil, préférences, export et suppression des données (F-CPT-05/06, §8.3)."""

from __future__ import annotations

import os
import shutil
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import billing_service, security
from ..config import settings
from ..db import get_db
from ..deps import api_error, current_user
from ..engine.subtitles import STYLES
from ..models import Project, Upload, User
from ..serializers import project_out, user_out
import contextlib

router = APIRouter(prefix="/api/me", tags=["profil"])


class PrefsIn(BaseModel):
    language: Literal["auto", "fr", "en"] | None = None
    subtitle_style: str | None = None
    format: Literal["9:16", "1:1", "original"] | None = None
    notify_email: bool | None = None
    auto_analyse: bool | None = None


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # Facultatif ; chaîne vide = retirer l'adresse. Sert à récupérer le mot de passe.
    email: EmailStr | Literal[""] | None = None
    prefs: PrefsIn | None = None


class PasswordIn(BaseModel):
    # Inutile pour un compte Google qui n'a pas encore de mot de passe.
    current_password: str = Field(default="", max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class DeleteIn(BaseModel):
    # Mot de passe, ou nom d'utilisateur pour un compte Google sans mot de passe.
    password: str = Field(max_length=200)


def _confirms_identity(user: User, secret: str) -> bool:
    if user.password_hash:
        return security.verify_password(secret, user.password_hash)
    return bool(secret) and secret.strip().lower() == (user.username or "")


@router.get("")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = user_out(user)
    db.commit()  # persiste un éventuel changement de période de quota
    return data


@router.patch("")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip()
    if body.email is not None:
        email = body.email.lower() or None
        if email and email != user.email:
            if db.scalar(select(User.id).where(func.lower(User.email) == email, User.id != user.id)):
                raise api_error(409, "email_taken", "Cette adresse e-mail est déjà utilisée par un autre compte.")
        if not email and user.google_sub:
            raise api_error(422, "email_required", "L’adresse d’un compte Google ne peut pas être retirée.")
        user.email = email
    if body.prefs is not None:
        changes = body.prefs.model_dump(exclude_none=True)
        if "subtitle_style" in changes and changes["subtitle_style"] not in STYLES:
            raise api_error(422, "invalid_style", "Style de sous-titres inconnu.")
        user.prefs = {**user.preferences(), **changes}  # réassignation : JSON détecté comme modifié
    db.commit()
    return user_out(user)


@router.post("/password")
def change_password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.password_hash and not security.verify_password(body.current_password, user.password_hash):
        raise api_error(400, "bad_password", "Mot de passe actuel incorrect.")
    user.password_hash = security.hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    return {"access_token": security.access_token(user), "user": user_out(user)}


@router.get("/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Droit d'accès : toutes les données personnelles détenues sur le compte."""
    projects = db.scalars(select(Project).where(Project.user_id == user.id)).all()
    return {
        "account": user_out(user),
        "projects": [project_out(p, user) for p in projects],
    }


@router.delete("")
def delete_me(body: DeleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not _confirms_identity(user, body.password):
        raise api_error(
            400,
            "bad_password",
            "Mot de passe incorrect." if user.password_hash else "Saisissez votre nom d’utilisateur pour confirmer.",
        )
    billing_service.cancel_subscription(user)
    for project in db.scalars(select(Project).where(Project.user_id == user.id)).all():
        shutil.rmtree(settings.projects_dir / project.id, ignore_errors=True)
    for upload in db.scalars(select(Upload).where(Upload.user_id == user.id)).all():
        if not upload.consumed:
            with contextlib.suppress(OSError):
                os.remove(upload.path)
    db.delete(user)
    db.commit()
    return {"message": "Votre compte et toutes vos données ont été supprimés."}
