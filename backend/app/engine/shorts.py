"""Shorts : extraction de plusieurs vidéos courtes depuis une vidéo importée.

Les extraits sont choisis dans la timeline déjà débarrassée des silences :
- ils commencent au début d'une phrase et se terminent à la fin d'une phrase,
  pour ne jamais couper la parole au milieu d'un mot ;
- on privilégie les passages où la parole est la plus dense (le plus de mots par seconde) ;
- les extraits ne se chevauchent pas.
"""

from __future__ import annotations

import math

from .silences import Segment

MIN_DURATION = 30
MAX_DURATION = 150
MAX_COUNT = 10
DEFAULT_COUNT = 3
DEFAULT_DURATION = 30

Window = tuple[float, float]


def _snap(value: float, fps: float) -> float:
    """Aligne sur la grille des images : son et image restent synchronisés."""
    return round(round(value * fps) / fps, 6)


def _evenly_spaced(total: float, count: int, length: float) -> list[Window]:
    count = max(1, min(count, int(total // length) or 1))
    if count == 1:
        return [(0.0, min(total, length))]
    step = (total - length) / (count - 1)
    return [(i * step, i * step + length) for i in range(count)]


def select_windows(
    phrases: list[dict],
    total: float,
    count: int,
    length: float,
    fps: float = 30.0,
) -> list[Window]:
    """Fenêtres [début, fin) dans la timeline coupée, triées chronologiquement."""
    if total <= 0:
        return []
    if total <= length + 0.5:
        return [(0.0, _snap(total, fps))]

    spans = [
        (p["words"][0]["s"], p["words"][-1]["e"], len(p["words"]))
        for p in phrases
        if p.get("words")
    ]
    candidates: list[tuple[float, Window]] = []
    for i, (start, _end, _n) in enumerate(spans):
        if start + length * 0.5 > total:
            break
        end = start
        words = 0
        for _p_start, p_end, n in spans[i:]:
            if p_end - start > length:
                break
            end, words = p_end, words + n
        if end - start < length * 0.6:
            # Phrases trop longues pour tomber juste : on coupe à la durée demandée.
            end = min(total, start + length)
            words = sum(n for s, e, n in spans[i:] if e <= end)
        # Densité de parole, légèrement favorisée quand l'extrait remplit bien la durée.
        score = words / max(end - start, 1.0) + 0.5 * (end - start) / length
        candidates.append((score, (start, end)))

    if not candidates:
        windows = _evenly_spaced(total, count, length)
    else:
        windows: list[Window] = []
        for _score, (start, end) in sorted(candidates, key=lambda c: c[0], reverse=True):
            if all(end + 0.5 <= s or start >= e + 0.5 for s, e in windows):
                windows.append((start, end))
                if len(windows) >= count:
                    break
        if len(windows) < count:
            # Compléter avec des fenêtres régulières qui ne chevauchent pas les choisies.
            for start, end in _evenly_spaced(total, count * 3, length):
                if len(windows) >= count:
                    break
                if all(end + 0.5 <= s or start >= e + 0.5 for s, e in windows):
                    windows.append((start, end))

    snapped = []
    for start, end in sorted(windows):
        start = _snap(max(0.0, start - 0.15), fps)  # petite marge avant la première syllabe
        end = _snap(min(total, end + 0.25, start + length), fps)  # jamais plus que la durée choisie
        if end - start >= 1.0:
            snapped.append((start, end))
    return snapped


def source_segments(kept: list[Segment], window: Window) -> list[Segment]:
    """Traduit une fenêtre de la timeline coupée en plages de la vidéo source."""
    start, end = window
    out: list[Segment] = []
    cursor = 0.0
    for s, e in kept:
        seg_start, seg_end = cursor, cursor + (e - s)
        lo, hi = max(start, seg_start), min(end, seg_end)
        if hi - lo > 1e-6:
            out.append((round(s + lo - seg_start, 6), round(s + hi - seg_start, 6)))
        cursor = seg_end
        if cursor >= end:
            break
    return out


def words_in_window(words: list[dict], window: Window) -> list[dict]:
    """Mots de la fenêtre, recalés sur le début du short."""
    start, end = window
    out = []
    for word in words:
        if word["s"] >= start - 0.05 and word["e"] <= end + 0.3:
            out.append(
                {
                    "w": word["w"],
                    "s": round(max(0.0, word["s"] - start), 3),
                    "e": round(min(end - start, word["e"] - start), 3),
                }
            )
    return out


def title_for(words: list[dict], fallback: str) -> str:
    text = " ".join(w["w"] for w in words[:9]).strip()
    if not text:
        return fallback
    return text + ("…" if len(words) > 9 else "")


def clamp(count: int, duration: float) -> tuple[int, int]:
    count = max(1, min(MAX_COUNT, int(count or DEFAULT_COUNT)))
    duration = int(max(MIN_DURATION, min(MAX_DURATION, math.floor(float(duration or DEFAULT_DURATION)))))
    return count, duration
