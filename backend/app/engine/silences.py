"""Détection des silences (F-TRT-01) et calcul des plages conservées (F-TRT-02)."""

from __future__ import annotations

import math
import re
from pathlib import Path

from . import ffmpeg

Segment = tuple[float, float]

_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect(path: Path, duration: float, noise_db: float = -35.0, min_silence: float = 0.5) -> list[Segment]:
    stderr = ffmpeg.run(
        [
            "-i",
            str(path),
            "-vn",
            "-sn",
            "-dn",
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ]
    )
    return parse_silencedetect(stderr, duration)


def parse_silencedetect(stderr: str, duration: float) -> list[Segment]:
    silences: list[Segment] = []
    start: float | None = None
    for line in stderr.splitlines():
        if (m := _START.search(line)) is not None:
            start = max(0.0, float(m.group(1)))
        elif (m := _END.search(line)) is not None and start is not None:
            silences.append((start, min(duration, float(m.group(1)))))
            start = None
    if start is not None and start < duration:
        silences.append((start, duration))
    return silences


def _merge(segments: list[Segment], gap: float = 0.0) -> list[Segment]:
    merged: list[Segment] = []
    for s, e in sorted(segments):
        if merged and s <= merged[-1][1] + gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def keep_segments(
    silences: list[Segment],
    duration: float,
    padding: float = 0.1,
    fps: float = 30.0,
) -> list[Segment]:
    """Plages de parole à conserver, élargies de `padding` (respiration) et alignées sur les images.

    L'alignement sur la grille d'images garantit que la vidéo et l'audio coupés gardent
    exactement la même durée par plage : aucune dérive de synchronisation.
    """
    if duration <= 0:
        return []
    speech: list[Segment] = []
    cursor = 0.0
    for s, e in _merge(silences):
        if s > cursor:
            speech.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        speech.append((cursor, duration))

    frame = 1.0 / fps
    padded = [(max(0.0, s - padding), min(duration, e + padding)) for s, e in speech]
    snapped = []
    for s, e in _merge(padded):
        s2 = math.floor(s / frame + 1e-6) * frame
        e2 = min(duration, math.ceil(e / frame - 1e-6) * frame)
        if e2 - s2 >= frame:
            snapped.append((round(s2, 6), round(e2, 6)))
    kept = _merge(snapped)
    total = sum(e - s for s, e in kept)
    if total < 0.5:
        # Vidéo entièrement silencieuse (ou presque) : on ne coupe rien plutôt que de tout vider.
        return [(0.0, round(duration, 6))]
    return kept


def removed_count(kept: list[Segment], duration: float) -> int:
    """Nombre de plages supprimées (début, entre-deux et fin)."""
    if not kept:
        return 0
    count = len(kept) - 1
    if kept[0][0] > 0.01:
        count += 1
    if duration - kept[-1][1] > 0.01:
        count += 1
    return count


def or_expr(terms: list[str]) -> str:
    """Somme de termes sous forme d'arbre équilibré.

    L'analyseur d'expressions de FFmpeg refuse une chaîne « a+b+c+… » de 100 termes ou plus
    (« Cannot allocate memory ») ; un arbre « ((a+b)+(c+d)) » n'a pas cette limite.
    """
    if not terms:
        return "0"
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({or_expr(terms[:middle])}+{or_expr(terms[middle:])})"


def video_select_expr(kept: list[Segment], fps: float) -> str:
    # Décalage d'une demi-image pour ne pas dépendre de l'arrondi des timestamps.
    half = 0.5 / fps
    return or_expr([f"gte(t,{s - half:.6f})*lt(t,{e - half:.6f})" for s, e in kept])
