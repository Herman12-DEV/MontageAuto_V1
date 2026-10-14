"""Représentations JSON renvoyées au frontend."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import plans, security
from .config import settings
from .engine import pipeline
from .models import Project, User


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.name or user.username or "",
        "has_password": bool(user.password_hash),
        "google_linked": bool(user.google_sub),
        "plan": user.plan,
        "plan_renews_at": _iso(user.plan_renews_at),
        "has_subscription": bool(user.stripe_subscription_id),
        "prefs": user.preferences(),
        "quota": plans.quota(user),
        "created_at": _iso(user.created_at),
    }


def _queue_position(db: Session, project: Project) -> int | None:
    if project.status != "queued":
        return None
    ahead = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(
            Project.status == "queued",
            or_(
                Project.priority > project.priority,
                (Project.priority == project.priority) & (Project.created_at < project.created_at),
            ),
        )
    )
    return int(ahead or 0) + 1


def project_out(project: Project, user: User, db: Session | None = None, *, detail: bool = False) -> dict:
    workdir = settings.projects_dir / project.id
    options = project.options or {}
    shorts_mode = options.get("mode") == "shorts"
    data = {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "job_kind": project.job_kind,
        "stage": project.stage,
        "progress": round(project.progress or 0.0, 4),
        "error": project.error,
        "source_kind": project.source_kind,
        "source_filename": project.source_filename,
        "storage_path": project.storage_path,
        "options": project.options,
        "duration_in": project.duration_in,
        "duration_out": project.duration_out,
        "cuts": project.cuts,
        "saved_pct": (
            round(100 * (1 - project.duration_out / project.duration_in), 1)
            if project.duration_in and project.duration_out and not shorts_mode
            else None
        ),
        "mode": "shorts" if shorts_mode else "full",
        "language": project.language,
        "width": project.width,
        "height": project.height,
        "fps": project.fps,
        "created_at": _iso(project.created_at),
        "finished_at": _iso(project.finished_at),
        "expires_at": _iso(project.expires_at),
    }
    if detail:
        token = security.media_token(user, project.id)
        base = f"/api/files/{project.id}"
        media = {}
        has_video = (workdir / "output.mp4").exists()
        if has_video:
            media["video"] = f"{base}/video?token={token}"
            media["video_download"] = f"{base}/video?token={token}&download=1"
        for kind, name in (("srt", "subtitles.srt"), ("ass", "subtitles.ass"), ("txt", "transcript.txt")):
            if (workdir / name).exists():
                media[kind] = f"{base}/{kind}?token={token}&download=1"
        if shorts_mode:
            items = []
            for item in pipeline.load_shorts(workdir):
                if not (workdir / item["video"]).exists():
                    continue
                n = item["index"]
                items.append(
                    {
                        "index": n,
                        "title": item["title"],
                        "duration": item["duration"],
                        "video": f"{base}/short-{n}?token={token}",
                        "video_download": f"{base}/short-{n}?token={token}&download=1",
                        "srt": f"{base}/short-{n}-srt?token={token}&download=1" if item.get("srt") else None,
                    }
                )
            media["shorts"] = items
        data["media"] = media
        data["has_transcript"] = (workdir / "transcript.json").exists()
        data["queue_position"] = _queue_position(db, project) if db is not None else None
    return data
