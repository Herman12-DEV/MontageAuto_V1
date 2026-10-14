"""Montages : création, suivi, relance, édition des sous-titres, fichiers (F-TRT, F-ST, F-RES)."""

from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import firebase, plans, security
from ..config import settings
from ..db import get_db
from ..deps import api_error, current_user
from ..engine import EngineError, pipeline, subtitles, youtube
from ..models import Project, Upload, User, utcnow
from ..ratelimit import limit
from ..serializers import project_out

router = APIRouter(tags=["montages"])


class StorageSource(BaseModel):
    """Vidéo déjà envoyée par l'interface dans Firebase Storage."""

    path: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2000)
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)


class ProjectIn(BaseModel):
    upload_id: str | None = None
    storage: StorageSource | None = None
    youtube_url: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=200)
    options: dict = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class RerenderIn(BaseModel):
    options: dict = Field(default_factory=dict)


class PhraseEdit(BaseModel):
    index: int = Field(ge=0)
    text: str = Field(max_length=2000)


class TranscriptIn(BaseModel):
    phrases: list[PhraseEdit] = Field(max_length=5000)


# Options modifiables sans refaire l'analyse ni la transcription.
COSMETIC_OPTIONS = {
    "subtitle_style", "format", "music", "music_volume", "subtitles", "mode", "shorts_count", "shorts_duration",
}


def _get(db: Session, project_id: str, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise api_error(404, "not_found", "Montage introuvable.")
    return project


def _ensure_capacity(db: Session, user: User) -> None:
    plan = plans.plan_for(user)
    active = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.user_id == user.id, Project.status.in_(("queued", "processing")))
    )
    if active >= plan.max_active_jobs:
        message = (
            "Un montage est déjà en cours. Attendez qu’il se termine ou passez au plan Pro "
            "pour traiter plusieurs vidéos à la fois."
            if plan.key == "free"
            else f"Vous avez déjà {active} montages en file (maximum {plan.max_active_jobs})."
        )
        raise api_error(429, "too_many_active", message)


def _ensure_credit(user: User) -> None:
    if not plans.has_credit(user):
        raise api_error(
            402,
            "quota_exceeded",
            "Vous avez utilisé vos montages gratuits du mois. Passez au plan Pro pour continuer "
            "sans limite.",
        )


def _ensure_duration(user: User, duration: float) -> None:
    plan = plans.plan_for(user)
    if duration > plan.max_duration_s + 1:
        hint = " Passez au plan Pro pour monter des vidéos jusqu’à 30 min." if plan.key == "free" else ""
        raise api_error(
            422,
            "too_long",
            f"Cette vidéo dure {duration / 60:.1f} min : votre offre est limitée à "
            f"{plan.max_duration_s // 60} min.{hint}",
        )


@router.post("/api/projects", status_code=201, dependencies=[Depends(limit("project", 30, 3600))])
def create_project(body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if sum(bool(x) for x in (body.upload_id, body.youtube_url, body.storage)) != 1:
        raise api_error(422, "bad_source", "Indiquez une vidéo téléversée ou une URL YouTube.")
    if body.storage:
        if not user.firebase_uid:
            raise api_error(403, "firebase_required", "Connectez-vous avec votre compte pour importer une vidéo.")
        try:
            firebase.validate_storage_source(user.firebase_uid, body.storage.path, body.storage.url)
        except firebase.FirebaseError as exc:
            raise api_error(422, "bad_storage", str(exc)) from exc
        if body.storage.size > settings.max_upload_bytes:
            raise api_error(413, "too_large", "La vidéo dépasse la limite de 500 Mo.")
        if _extension_ok(body.storage.filename) is False:
            raise api_error(422, "bad_format", "Format non pris en charge. Choisissez une vidéo MP4, MOV, WebM ou MKV.")
    _ensure_capacity(db, user)
    _ensure_credit(user)

    prefs = user.preferences()
    defaults = {k: prefs[k] for k in ("language", "subtitle_style", "format")}
    options = pipeline.normalize_options({**defaults, **body.options})
    plan = plans.plan_for(user)
    project = Project(
        user_id=user.id,
        title="",
        options=options,
        priority=plan.priority,
        expires_at=utcnow() + timedelta(days=settings.retention_days),
    )

    if body.upload_id:
        upload = db.get(Upload, body.upload_id)
        if upload is None or upload.user_id != user.id or upload.consumed:
            raise api_error(404, "upload_not_found", "Fichier introuvable : téléversez-le à nouveau.")
        if not upload.completed or not upload.probe:
            raise api_error(409, "upload_incomplete", "Le téléversement n’est pas terminé.")
        _ensure_duration(user, upload.probe["duration"])
        project.source_kind = "upload"
        project.source_filename = upload.filename
        project.duration_in = upload.probe["duration"]
        project.title = (body.title or Path(upload.filename).stem)[:200]
        db.add(project)
        db.flush()
        workdir = settings.projects_dir / project.id
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.move(upload.path, workdir / f"source{Path(upload.path).suffix.lower()}")
        upload.consumed = True
    elif body.storage:
        # Durée vérifiée par le worker après téléchargement (comme pour YouTube).
        project.source_kind = "storage"
        project.source_url = body.storage.url
        project.storage_path = body.storage.path
        project.source_filename = Path(body.storage.filename).name[:255]
        project.title = (body.title or Path(body.storage.filename).stem)[:200]
        db.add(project)
        db.flush()
        (settings.projects_dir / project.id).mkdir(parents=True, exist_ok=True)
    else:
        url = body.youtube_url.strip()
        if not youtube.is_youtube_url(url):
            raise api_error(422, "bad_url", "Collez un lien YouTube valide (youtube.com ou youtu.be).")
        try:
            info = youtube.fetch_info(url)
        except EngineError as exc:
            raise api_error(422, "youtube_error", str(exc)) from exc
        if info["duration"]:
            _ensure_duration(user, info["duration"])
        project.source_kind = "youtube"
        project.source_url = url
        project.source_filename = info["title"][:255]
        project.duration_in = info["duration"] or None
        project.title = (body.title or info["title"])[:200]
        db.add(project)
        db.flush()
        (settings.projects_dir / project.id).mkdir(parents=True, exist_ok=True)

    plans.charge_credit(user)
    project.credit_charged = True
    db.commit()
    return project_out(project, user, db, detail=True)


@router.get("/api/projects")
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    projects = db.scalars(
        select(Project)
        .where(Project.user_id == user.id, Project.expires_at > utcnow())
        .order_by(Project.created_at.desc())
    ).all()
    return {"projects": [project_out(p, user) for p in projects]}


@router.get("/api/projects/{project_id}")
def get_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return project_out(_get(db, project_id, user), user, db, detail=True)


@router.patch("/api/projects/{project_id}")
def rename_project(
    project_id: str, body: ProjectPatch, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Renommer un montage."""
    project = _get(db, project_id, user)
    project.title = body.title.strip()[:200]
    db.commit()
    return project_out(project, user, db, detail=True)


def _extension_ok(filename: str) -> bool:
    return filename.rsplit(".", 1)[-1].lower() in {"mp4", "mov", "webm", "mkv", "m4v"} if "." in filename else False


@router.post("/api/projects/{project_id}/retry")
def retry_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = _get(db, project_id, user)
    if project.status not in ("failed", "done"):
        raise api_error(409, "not_retryable", "Ce montage est déjà en cours de traitement.")
    workdir = settings.projects_dir / project.id
    if project.source_kind == "upload" and not any(workdir.glob("source.*")):
        raise api_error(410, "source_gone", "La vidéo d’origine n’est plus disponible : importez-la à nouveau.")
    _ensure_capacity(db, user)
    if project.status == "done":
        # Relancer un montage terminé = refaire toute l'analyse ; un échec rejoue le même job.
        project.job_kind = "full"
    if project.job_kind == "full":
        _ensure_credit(user)
        plans.charge_credit(user)
        project.credit_charged = True
        # Analyse complète : on repart de zéro.
        for name in (pipeline.ANALYSIS, pipeline.TRANSCRIPT):
            (workdir / name).unlink(missing_ok=True)
    project.status = "queued"
    project.stage = "attente"
    project.progress = 0.0
    project.error = None
    project.attempts = 0
    project.created_at = utcnow()
    db.commit()
    return project_out(project, user, db, detail=True)


@router.post("/api/projects/{project_id}/rerender")
def rerender_project(
    project_id: str, body: RerenderIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Change le style, le format ou la musique d'un montage terminé, sans crédit."""
    project = _get(db, project_id, user)
    if project.status != "done":
        raise api_error(409, "not_done", "Le montage doit être terminé pour être modifié.")
    _ensure_capacity(db, user)
    changes = {k: v for k, v in body.options.items() if k in COSMETIC_OPTIONS}
    project.options = pipeline.normalize_options({**(project.options or {}), **changes})
    _queue_rerender(project)
    db.commit()
    return project_out(project, user, db, detail=True)


def _queue_rerender(project: Project) -> None:
    project.job_kind = "rerender"
    project.status = "queued"
    project.stage = "attente"
    project.progress = 0.0
    project.error = None
    project.attempts = 0
    project.credit_charged = False


@router.get("/api/projects/{project_id}/transcript")
def get_transcript(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = _get(db, project_id, user)
    transcript = pipeline.load_transcript(settings.projects_dir / project.id)
    if transcript is None:
        raise api_error(404, "no_transcript", "Aucune transcription pour ce montage.")
    return {
        "language": transcript.get("language"),
        "phrases": [
            {
                "index": i,
                "start": phrase["words"][0]["s"] if phrase["words"] else None,
                "end": phrase["words"][-1]["e"] if phrase["words"] else None,
                "text": " ".join(w["w"] for w in phrase["words"]),
            }
            for i, phrase in enumerate(transcript.get("phrases", []))
        ],
    }


@router.put("/api/projects/{project_id}/transcript")
def update_transcript(
    project_id: str, body: TranscriptIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """F-ST-06 : corrections manuelles, puis réincrustation automatique."""
    project = _get(db, project_id, user)
    if project.status != "done":
        raise api_error(409, "not_done", "Attendez la fin du montage pour corriger les sous-titres.")
    workdir = settings.projects_dir / project.id
    transcript = pipeline.load_transcript(workdir)
    if transcript is None:
        raise api_error(404, "no_transcript", "Aucune transcription pour ce montage.")
    phrases = transcript.get("phrases", [])
    changed = False
    for edit in body.phrases:
        if edit.index >= len(phrases):
            continue
        words = phrases[edit.index]["words"]
        current = " ".join(w["w"] for w in words)
        new_text = " ".join(edit.text.split())
        if new_text != current:
            phrases[edit.index]["words"] = subtitles.apply_phrase_edit(words, new_text)
            changed = True
    if changed:
        transcript["phrases"] = [p for p in phrases if p["words"]]
        pipeline.save_transcript(workdir, transcript)
        _ensure_capacity(db, user)
        _queue_rerender(project)
        db.commit()
    return project_out(project, user, db, detail=True)


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = _get(db, project_id, user)
    if project.status == "queued" and project.credit_charged:
        plans.refund_credit(user)  # jamais commencé : on rend le crédit
    db.delete(project)
    db.commit()
    shutil.rmtree(settings.projects_dir / project_id, ignore_errors=True)
    return {"message": "Montage supprimé."}


# --- Fichiers privés (NF-SEC-02) --------------------------------------------

FILES = {
    "video": ("output.mp4", "video/mp4", "mp4"),
    "srt": ("subtitles.srt", "application/x-subrip", "srt"),
    "ass": ("subtitles.ass", "text/x-ssa", "ass"),
    "txt": ("transcript.txt", "text/plain; charset=utf-8", "txt"),
}


def _slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-").lower()[:60] or "montage"


@router.get("/api/files/{project_id}/{kind}")
def get_file(
    project_id: str,
    kind: str,
    request: Request,
    token: str | None = Query(default=None),
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    short = re.fullmatch(r"short-(\d{1,2})(-srt)?", kind)
    if kind not in FILES and not short:
        raise api_error(404, "not_found", "Fichier introuvable.")
    user_id = None
    payload = security.decode(token, "media") if token else None
    if payload and payload.get("pid") == project_id:
        user_id = payload.get("sub")
    else:
        header = request.headers.get("authorization", "")
        access = security.decode(header[7:], "access") if header.lower().startswith("bearer ") else None
        user_id = access.get("sub") if access else None
    project = db.get(Project, project_id)
    if project is None or user_id is None or project.user_id != user_id:
        raise api_error(404, "not_found", "Fichier introuvable.")
    if short:
        n = int(short.group(1))
        name, media_type, ext = (
            (f"short_{n}.srt", "application/x-subrip", "srt")
            if short.group(2)
            else (f"short_{n}.mp4", "video/mp4", "mp4")
        )
        filename = f"{_slug(project.title)}-short-{n}.{ext}"
    else:
        name, media_type, ext = FILES[kind]
        filename = f"{_slug(project.title)}.{ext}"
    path = settings.projects_dir / project_id / name
    if not path.exists():
        raise api_error(404, "not_found", "Fichier introuvable.")
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename if download else None,
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, max-age=600"},
    )
