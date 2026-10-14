"""Téléversement par morceaux, avec reprise (F-UP-01, F-UP-02, F-UP-04, F-UP-05).

1. POST /api/uploads                 → crée la session (contrôle format + taille)
2. PUT  /api/uploads/{id}?offset=N   → envoie un morceau (corps binaire brut)
3. GET  /api/uploads/{id}            → octets déjà reçus (pour reprendre après coupure)
4. POST /api/uploads/{id}/complete   → vérifie que c'est une vraie vidéo (ffprobe)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import api_error, current_user
from ..engine import EngineError, ffmpeg
from ..models import Upload, User
from ..ratelimit import limit
import contextlib

router = APIRouter(prefix="/api/uploads", tags=["import"])

ALLOWED_EXTENSIONS = {"mp4", "mov", "webm", "mkv", "m4v"}
FORMAT_MESSAGE = "Format non pris en charge. Choisissez une vidéo MP4, MOV, WebM ou MKV."


class UploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def looks_like_video(head: bytes) -> bool:
    """Signature binaire : conteneur ISO-BMFF (MP4/MOV) ou Matroska (MKV/WebM)."""
    if len(head) >= 12 and head[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot"):
        return True
    return head[:4] == b"\x1a\x45\xdf\xa3"


def _get(db: Session, upload_id: str, user: User) -> Upload:
    upload = db.get(Upload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise api_error(404, "not_found", "Téléversement introuvable.")
    return upload


def _state(upload: Upload) -> dict:
    return {
        "upload_id": upload.id,
        "filename": upload.filename,
        "size": upload.size,
        "received": upload.received,
        "completed": upload.completed,
        "chunk_size": settings.upload_chunk_bytes,
        "probe": upload.probe,
    }


def _reject(db: Session, upload: Upload, code: str, message: str):
    with contextlib.suppress(OSError):
        os.remove(upload.path)
    db.delete(upload)
    db.commit()
    return api_error(422, code, message)


@router.post("", status_code=201, dependencies=[Depends(limit("upload", 30, 3600))])
def create_upload(body: UploadIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if _extension(body.filename) not in ALLOWED_EXTENSIONS:
        raise api_error(422, "bad_format", FORMAT_MESSAGE)
    if body.size > settings.max_upload_bytes:
        raise api_error(
            413,
            "too_large",
            f"La vidéo dépasse la limite de {settings.max_upload_bytes // (1024 * 1024)} Mo.",
        )
    upload = Upload(user_id=user.id, filename=Path(body.filename).name, size=body.size, path="")
    db.add(upload)
    db.flush()
    upload.path = str(settings.uploads_dir / f"{upload.id}.part")
    Path(upload.path).touch()
    db.commit()
    return _state(upload)


@router.get("/{upload_id}")
def upload_state(upload_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    upload = _get(db, upload_id, user)
    # La taille réelle sur disque fait foi (un morceau a pu être interrompu en cours d'écriture).
    on_disk = os.path.getsize(upload.path) if os.path.exists(upload.path) else 0
    if on_disk != upload.received and not upload.completed:
        upload.received = min(on_disk, upload.size)
        db.commit()
    return _state(upload)


@router.put("/{upload_id}")
async def upload_chunk(
    upload_id: str,
    request: Request,
    offset: int = Query(ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    upload = _get(db, upload_id, user)
    if upload.completed:
        raise api_error(409, "completed", "Ce fichier est déjà complet.")
    if offset != upload.received:
        raise api_error(
            409, "bad_offset", "Décalage inattendu : reprenez depuis la position indiquée.",
            received=upload.received,
        )
    limit_bytes = settings.upload_chunk_bytes + 1024
    written = 0
    head = b""
    with open(upload.path, "r+b") as handle:
        handle.seek(offset)
        handle.truncate()
        async for chunk in request.stream():
            if not chunk:
                continue
            if offset == 0 and len(head) < 16:
                head += chunk[: 16 - len(head)]
            written += len(chunk)
            if written > limit_bytes or offset + written > upload.size:
                handle.truncate(offset)
                raise api_error(413, "chunk_too_large", "Morceau trop volumineux.")
            handle.write(chunk)
    if offset == 0 and not looks_like_video(head):
        raise _reject(db, upload, "bad_format", FORMAT_MESSAGE)
    upload.received = offset + written
    db.commit()
    return {"received": upload.received}


@router.post("/{upload_id}/complete")
def complete_upload(upload_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    upload = _get(db, upload_id, user)
    if upload.completed:
        return _state(upload)
    if upload.received != upload.size:
        raise api_error(409, "incomplete", "Le fichier n’est pas encore entièrement envoyé.", received=upload.received)
    final = Path(upload.path).with_suffix("." + (_extension(upload.filename) or "mp4"))
    os.replace(upload.path, final)
    upload.path = str(final)
    try:
        info = ffmpeg.probe(final)
    except EngineError as exc:
        raise _reject(db, upload, "not_a_video", f"{exc} Vérifiez le fichier et réessayez.") from exc
    upload.probe = info
    upload.completed = True
    db.commit()
    return _state(upload)
