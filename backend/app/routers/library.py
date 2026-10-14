"""Catalogues publics (styles, musiques) et état du système."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import music
from ..config import settings
from ..db import get_db
from ..engine import ffmpeg
from ..engine.subtitles import public_styles
from ..models import Project, WorkerHeartbeat, utcnow

router = APIRouter(prefix="/api", tags=["catalogue"])


@router.get("/library")
def library():
    return {
        "styles": public_styles(),
        "music": music.list_tracks(),
        "formats": [
            {"key": "9:16", "label": "Vertical 9:16", "hint": "TikTok, Reels, Shorts"},
            {"key": "1:1", "label": "Carré 1:1", "hint": "Fil Instagram, LinkedIn"},
            {"key": "original", "label": "Format d’origine", "hint": "YouTube, site web"},
        ],
        "languages": [
            {"key": "auto", "label": "Détection automatique"},
            {"key": "fr", "label": "Français"},
            {"key": "en", "label": "Anglais"},
        ],
        "limits": {"max_upload_bytes": settings.max_upload_bytes, "retention_days": settings.retention_days},
    }


@router.get("/health")
def health(db: Session = Depends(get_db)):
    # Les workers signalent leur présence toutes les 15 s, y compris pendant un montage.
    recent = utcnow() - timedelta(seconds=max(45, settings.worker_poll_seconds * 10))
    workers = db.scalar(
        select(func.count()).select_from(WorkerHeartbeat).where(WorkerHeartbeat.last_seen > recent)
    )
    counts = dict(
        db.execute(
            select(Project.status, func.count())
            .where(Project.status.in_(("queued", "processing")))
            .group_by(Project.status)
        ).all()
    )
    engine_ok = ffmpeg.available()
    return {
        "status": "ok" if engine_ok and workers else "degraded",
        "ffmpeg": engine_ok,
        "workers": workers,
        "queue": {"queued": counts.get("queued", 0), "processing": counts.get("processing", 0)},
    }
