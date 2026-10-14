"""Bibliothèque musicale libre de droits avec registre des licences (F-HAB-01, §8.3)."""

from __future__ import annotations

import json
from pathlib import Path

from .config import settings

REGISTRY = "licenses.json"


def _registry_path() -> Path:
    return settings.music_dir / REGISTRY


def list_tracks() -> list[dict]:
    """Pistes déclarées dans licenses.json dont le fichier est bien présent."""
    path = _registry_path()
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    tracks = []
    for entry in entries:
        file = settings.music_dir / entry["file"]
        if file.exists() and entry.get("license"):
            tracks.append({k: v for k, v in entry.items() if k != "file"})
    return tracks


def track_path(track_id: str) -> Path | None:
    path = _registry_path()
    if not path.exists():
        return None
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if entry["id"] == track_id:
            file = (settings.music_dir / entry["file"]).resolve()
            if file.exists() and file.is_relative_to(settings.music_dir.resolve()):
                return file
    return None
