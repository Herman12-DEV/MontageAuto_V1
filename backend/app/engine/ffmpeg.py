"""Appels à FFmpeg / FFprobe."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from ..config import settings
from . import EngineError

_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _resolve(binary: str) -> str:
    found = shutil.which(binary)
    if found:
        return found
    if sys.platform == "win32":
        # Installation winget : le PATH de la session courante peut ne pas être à jour.
        candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links" / f"{binary}.exe"
        if candidate.exists():
            return str(candidate)
    return binary


@lru_cache
def ffmpeg_bin() -> str:
    return _resolve(settings.ffmpeg_bin)


@lru_cache
def ffprobe_bin() -> str:
    return _resolve(settings.ffprobe_bin)


@lru_cache
def ffmpeg_version() -> tuple[int, int] | None:
    try:
        out = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-version"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_CREATE_FLAGS,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"ffmpeg version n?(\d+)\.(\d+)", out)
    if not match:
        # Builds « git master » : on suppose une version récente.
        return (99, 0) if "ffmpeg version" in out else None
    return int(match.group(1)), int(match.group(2))


def available() -> bool:
    return ffmpeg_version() is not None


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    duration: float | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> str:
    """Lance ffmpeg ; renvoie stderr. `on_progress` reçoit une fraction 0..1."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y"]
    if on_progress and duration:
        cmd += ["-progress", "pipe:1", "-nostats"]
    cmd += args
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_CREATE_FLAGS,
    )
    stderr_chunks: list[str] = []

    def _drain() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_chunks.append(line)

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()
    assert proc.stdout is not None
    for line in proc.stdout:
        if on_progress and duration and line.startswith("out_time_us="):
            value = line.split("=", 1)[1].strip()
            if value.isdigit():
                on_progress(min(1.0, int(value) / 1_000_000 / duration))
    proc.wait()
    reader.join(timeout=5)
    stderr = "".join(stderr_chunks)
    if proc.returncode != 0:
        tail = "\n".join(stderr.strip().splitlines()[-12:])
        raise EngineError(f"FFmpeg a échoué (code {proc.returncode}).\n{tail}")
    return stderr


def probe(path: Path) -> dict:
    """Informations essentielles d'un média. Lève EngineError si ce n'est pas une vidéo."""
    try:
        result = subprocess.run(
            [
                ffprobe_bin(),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=_CREATE_FLAGS,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineError("Analyse du fichier impossible (délai dépassé).") from exc
    if result.returncode != 0:
        raise EngineError("Ce fichier n’est pas une vidéo lisible.")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video"
            and (s.get("disposition") or {}).get("attached_pic") != 1
        ),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise EngineError("Ce fichier ne contient aucune piste vidéo.")
    duration = _float(data.get("format", {}).get("duration")) or _float(video.get("duration"))
    if not duration or duration <= 0:
        raise EngineError("Durée de la vidéo illisible.")
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    rotation = _rotation(video)
    if rotation in (90, 270):
        width, height = height, width
    return {
        "duration": round(duration, 3),
        "width": width,
        "height": height,
        "fps": _fps(video),
        "has_audio": audio is not None,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "format": data.get("format", {}).get("format_name", ""),
    }


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key) or "0/0"
        num, _, den = raw.partition("/")
        try:
            value = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            continue
        if 1 <= value <= 240:
            return round(value, 3)
    return 30.0


def _rotation(stream: dict) -> int:
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        try:
            return abs(int(tags["rotate"])) % 360
        except ValueError:
            return 0
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                return abs(int(side["rotation"])) % 360
            except (TypeError, ValueError):
                return 0
    return 0


def filter_script_args(option: str, script: Path) -> list[str]:
    """Passe un graphe de filtres via un fichier (évite la limite de longueur des lignes de commande)."""
    version = ffmpeg_version() or (0, 0)
    if version >= (7, 0):
        return [f"-/{option.lstrip('-')}", script.name]
    return [f"{option}_script", script.name]
