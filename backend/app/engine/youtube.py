"""Import par URL YouTube (F-UP-03) via yt-dlp.

L'utilisateur déclare dans les CGU détenir les droits sur la vidéo importée (§8.3).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from ..config import settings
from . import EngineError, ffmpeg

_YOUTUBE = re.compile(
    r"^https?://(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[\w-]{6,}", re.I
)


def is_youtube_url(url: str) -> bool:
    return bool(_YOUTUBE.match(url.strip()))


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }


def fetch_info(url: str) -> dict:
    """Titre et durée, sans télécharger : permet de refuser tôt une vidéo trop longue."""
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp lève des types variés
        raise EngineError("Impossible de lire cette vidéo YouTube (privée, supprimée ou bloquée).") from exc
    if info.get("is_live"):
        raise EngineError("Les directs YouTube ne sont pas pris en charge.")
    return {"title": info.get("title") or "Vidéo YouTube", "duration": float(info.get("duration") or 0)}


def download(url: str, workdir: Path, on_progress: Callable[[float], None] | None = None) -> Path:
    import yt_dlp

    def hook(status: dict) -> None:
        if on_progress and status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            if total:
                on_progress(min(1.0, status.get("downloaded_bytes", 0) / total))

    opts = {
        **_base_opts(),
        # 1080p si le fichier tient dans la limite (≈ 450 Mo de vidéo + l'audio), sinon 720p, puis 480p.
        "format": (
            "bv*[height<=1080][filesize_approx<450M]+ba/bv*[height<=1080][filesize<450M]+ba"
            "/bv*[height<=720]+ba/bv*[height<=480]+ba/b[height<=720]/b"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / "source.%(ext)s"),
        "max_filesize": settings.max_upload_bytes,
        "ffmpeg_location": str(Path(ffmpeg.ffmpeg_bin()).parent),
        "progress_hooks": [hook],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise EngineError("Le téléchargement de la vidéo YouTube a échoué.") from exc
    files = [p for p in workdir.glob("source.*") if not p.name.endswith((".part", ".ytdl"))]
    if not files:
        raise EngineError("La vidéo YouTube dépasse la taille maximale autorisée (500 Mo).")
    return files[0]
