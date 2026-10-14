"""Chaîne complète d'un montage (§7.2) : analyse → transcription → montage → encodage."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .. import music
from . import EngineError, ffmpeg, render, shorts, silences, subtitles, transcribe

log = logging.getLogger(__name__)

# Bornes de progression globale de chaque étape (F-TRT-04).
STAGES = {
    "analyse": (0.0, 0.15),
    "transcription": (0.15, 0.55),
    "montage": (0.55, 0.6),
    "encodage": (0.6, 1.0),
}

DEFAULT_OPTIONS = {
    "silence_db": -35.0,
    "min_silence": 0.5,
    "padding_ms": 100,
    "language": "auto",
    "subtitles": True,
    "subtitle_style": subtitles.DEFAULT_STYLE,
    "format": "9:16",
    "music": None,
    "music_volume": 0.5,
    "cut_silences": True,
    # « full » = un montage complet ; « shorts » = plusieurs vidéos courtes extraites.
    "mode": "full",
    "shorts_count": shorts.DEFAULT_COUNT,
    "shorts_duration": shorts.DEFAULT_DURATION,
}

TRANSCRIPT = "transcript.json"
ANALYSIS = "analysis.json"
SHORTS = "shorts.json"


def normalize_options(raw: dict | None) -> dict:
    opts = {**DEFAULT_OPTIONS, **{k: v for k, v in (raw or {}).items() if k in DEFAULT_OPTIONS}}
    opts["silence_db"] = float(min(-10.0, max(-70.0, float(opts["silence_db"]))))
    opts["min_silence"] = float(min(5.0, max(0.2, float(opts["min_silence"]))))
    opts["padding_ms"] = int(min(1000, max(0, int(opts["padding_ms"]))))
    opts["music_volume"] = float(min(1.0, max(0.05, float(opts["music_volume"]))))
    if opts["language"] not in ("auto", *transcribe.SUPPORTED_LANGUAGES):
        opts["language"] = "auto"
    if opts["format"] not in render.FORMATS:
        opts["format"] = "9:16"
    if opts["subtitle_style"] not in subtitles.STYLES:
        opts["subtitle_style"] = subtitles.DEFAULT_STYLE
    if opts["music"] and music.track_path(str(opts["music"])) is None:
        opts["music"] = None
    opts["subtitles"] = bool(opts["subtitles"])
    opts["cut_silences"] = bool(opts["cut_silences"])
    if opts["mode"] not in ("full", "shorts"):
        opts["mode"] = "full"
    try:
        opts["shorts_count"], opts["shorts_duration"] = shorts.clamp(
            opts["shorts_count"], opts["shorts_duration"]
        )
    except (TypeError, ValueError):
        opts["shorts_count"], opts["shorts_duration"] = shorts.DEFAULT_COUNT, shorts.DEFAULT_DURATION
    return opts


@dataclass
class JobResult:
    duration_in: float
    duration_out: float
    cuts: int
    language: str | None
    width: int
    height: int
    fps: float
    files: dict[str, str] = field(default_factory=dict)
    shorts: list[dict] = field(default_factory=list)


class Progress:
    def __init__(self, report: Callable[[str, float], None]):
        self._report = report

    def stage(self, name: str, fraction: float = 0.0) -> None:
        lo, hi = STAGES[name]
        self._report(name, lo + (hi - lo) * max(0.0, min(1.0, fraction)))

    def callback(self, name: str) -> Callable[[float], None]:
        return lambda fraction: self.stage(name, fraction)


def _find_source(workdir: Path) -> Path:
    for path in workdir.glob("source.*"):
        return path
    raise EngineError("Fichier source introuvable : il a peut-être expiré.")


def load_transcript(workdir: Path) -> dict | None:
    path = workdir / TRANSCRIPT
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_transcript(workdir: Path, data: dict) -> None:
    (workdir / TRANSCRIPT).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def flat_words(transcript: dict | None) -> list[dict]:
    if not transcript:
        return []
    return [w for phrase in transcript.get("phrases", []) for w in phrase["words"]]


def run(
    workdir: Path,
    options: dict,
    *,
    watermark: str | None,
    report: Callable[[str, float], None],
    rerender: bool = False,
) -> JobResult:
    """Exécute le montage dans `workdir` (qui contient source.*). Idempotent."""
    progress = Progress(report)
    opts = normalize_options(options)
    source = _find_source(workdir)

    # [3] Analyse
    progress.stage("analyse")
    info = ffmpeg.probe(source)
    fps = render.output_fps(info["fps"])
    analysis_file = workdir / ANALYSIS
    if rerender and analysis_file.exists():
        kept = [tuple(seg) for seg in json.loads(analysis_file.read_text())["kept"]]
    else:
        if info["has_audio"] and opts["cut_silences"]:
            found = silences.detect(
                source, info["duration"], opts["silence_db"], opts["min_silence"]
            )
            kept = silences.keep_segments(
                found, info["duration"], opts["padding_ms"] / 1000, fps
            )
        else:
            kept = [(0.0, info["duration"])]
        analysis_file.write_text(json.dumps({"kept": kept, "probe": info}))
    duration_out = sum(e - s for s, e in kept)
    cuts = silences.removed_count(kept, info["duration"])
    progress.stage("analyse", 1.0)

    # [5] Transcription (sur l'audio déjà coupé : horodatages = timeline finale)
    transcript = load_transcript(workdir) if rerender else None
    if transcript is None and opts["subtitles"] and info["has_audio"]:
        progress.stage("transcription")
        speech = render.extract_cut_audio(source, kept, info["duration"], workdir)
        try:
            result = transcribe.transcribe_isolated(
                speech, duration_out, opts["language"], progress.callback("transcription")
            )
        finally:
            speech.unlink(missing_ok=True)
        transcript = {
            "language": result["language"],
            "phrases": subtitles.phrases_from_words(result["words"]),
        }
        save_transcript(workdir, transcript)
    progress.stage("transcription", 1.0)

    out_w, out_h = render.output_size(opts["format"], info["width"], info["height"])
    if opts["mode"] == "shorts":
        return _run_shorts(
            workdir, source, info, kept, cuts, transcript, opts, watermark, progress, rerender, fps, (out_w, out_h)
        )
    _clear_shorts(workdir)

    # [6] Montage : sous-titres stylés + filigrane
    progress.stage("montage")
    words = flat_words(transcript) if opts["subtitles"] else []
    files: dict[str, str] = {}
    subs_name = None
    if words or watermark:
        ass = subtitles.build_ass(
            words,
            opts["subtitle_style"],
            out_w,
            out_h,
            watermark=watermark,
            total_duration=duration_out,
        )
        (workdir / "render.ass").write_text(ass, encoding="utf-8")
        subs_name = "render.ass"
    if words:
        # Fichiers téléchargeables : sans filigrane, pour un usage dans d'autres logiciels.
        (workdir / "subtitles.ass").write_text(
            subtitles.build_ass(
                words, opts["subtitle_style"], out_w, out_h, total_duration=duration_out
            ),
            encoding="utf-8",
        )
        (workdir / "subtitles.srt").write_text(
            subtitles.build_srt(words, opts["subtitle_style"]), encoding="utf-8"
        )
        (workdir / "transcript.txt").write_text(subtitles.plain_text(words), encoding="utf-8")
        files.update(ass="subtitles.ass", srt="subtitles.srt", txt="transcript.txt")
    else:
        for name in ("subtitles.ass", "subtitles.srt", "transcript.txt"):
            (workdir / name).unlink(missing_ok=True)
    progress.stage("montage", 1.0)

    # [7-8] Encodage final
    progress.stage("encodage")
    track = music.track_path(opts["music"]) if opts["music"] else None
    tmp_name = "output.tmp.mp4"
    render.render(
        source=source,
        workdir=workdir,
        kept=kept,
        probe=info,
        fmt=opts["format"],
        subtitles_file=subs_name,
        music=track,
        music_volume=opts["music_volume"],
        out_name=tmp_name,
        on_progress=progress.callback("encodage"),
    )
    (workdir / tmp_name).replace(workdir / "output.mp4")
    files["video"] = "output.mp4"
    progress.stage("encodage", 1.0)

    return JobResult(
        duration_in=info["duration"],
        duration_out=round(duration_out, 3),
        cuts=cuts,
        language=(transcript or {}).get("language"),
        width=out_w,
        height=out_h,
        fps=fps,
        files=files,
    )


# --- Shorts ----------------------------------------------------------------------------


def _clear_shorts(workdir: Path) -> None:
    (workdir / SHORTS).unlink(missing_ok=True)
    for path in workdir.glob("short_*"):
        path.unlink(missing_ok=True)


def load_shorts(workdir: Path) -> list[dict]:
    path = workdir / SHORTS
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("shorts", [])


def _run_shorts(
    workdir: Path,
    source: Path,
    info: dict,
    kept: list,
    cuts: int,
    transcript: dict | None,
    opts: dict,
    watermark: str | None,
    progress: Progress,
    rerender: bool,
    fps: float,
    size: tuple[int, int],
) -> JobResult:
    """Plusieurs vidéos courtes, chacune avec ses sous-titres, sa musique et son filigrane."""
    progress.stage("montage")
    out_w, out_h = size
    duration_cut = sum(e - s for s, e in kept)
    all_words = flat_words(transcript)
    words = all_words if opts["subtitles"] else []
    count, length = opts["shorts_count"], opts["shorts_duration"]

    # Fenêtres conservées lors d'un nouveau rendu (style, format, correction des sous-titres).
    stored = json.loads((workdir / SHORTS).read_text(encoding="utf-8")) if (workdir / SHORTS).exists() else {}
    if rerender and stored.get("count") == count and stored.get("duration") == length:
        windows = [(item["start"], item["end"]) for item in stored["shorts"]]
    else:
        windows = shorts.select_windows(
            (transcript or {}).get("phrases", []), duration_cut, count, length, fps
        )
    if not windows:
        raise EngineError("Aucun extrait exploitable dans cette vidéo.")

    for name in ("subtitles.ass", "subtitles.srt", "output.mp4", "render.ass"):
        (workdir / name).unlink(missing_ok=True)
    for path in workdir.glob("short_*"):
        path.unlink(missing_ok=True)
    files: dict[str, str] = {}
    if all_words:
        (workdir / "transcript.txt").write_text(subtitles.plain_text(all_words), encoding="utf-8")
        files["txt"] = "transcript.txt"
    progress.stage("montage", 1.0)

    progress.stage("encodage")
    track = music.track_path(opts["music"]) if opts["music"] else None
    results: list[dict] = []
    for index, window in enumerate(windows, start=1):
        start, end = window
        clip = shorts.source_segments(kept, window)
        clip_words = shorts.words_in_window(words, window)
        clip_duration = sum(e - s for s, e in clip)
        subs_name = None
        if clip_words or watermark:
            subs_name = f"short_{index}.ass"
            (workdir / subs_name).write_text(
                subtitles.build_ass(
                    clip_words, opts["subtitle_style"], out_w, out_h,
                    watermark=watermark, total_duration=clip_duration,
                ),
                encoding="utf-8",
            )
        srt_name = None
        if clip_words:
            srt_name = f"short_{index}.srt"
            (workdir / srt_name).write_text(
                subtitles.build_srt(clip_words, opts["subtitle_style"]), encoding="utf-8"
            )

        def on_clip_progress(fraction: float, done: int = index - 1) -> None:
            progress.stage("encodage", (done + fraction) / len(windows))

        render.render(
            source=source,
            workdir=workdir,
            kept=clip,
            probe=info,
            fmt=opts["format"],
            subtitles_file=subs_name,
            music=track,
            music_volume=opts["music_volume"],
            out_name=f"short_{index}.tmp.mp4",
            on_progress=on_clip_progress,
        )
        (workdir / f"short_{index}.tmp.mp4").replace(workdir / f"short_{index}.mp4")
        results.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "duration": round(clip_duration, 3),
                "title": shorts.title_for(shorts.words_in_window(all_words, window), f"Short {index}"),
                "video": f"short_{index}.mp4",
                "srt": srt_name,
            }
        )
    (workdir / SHORTS).write_text(
        json.dumps({"count": count, "duration": length, "shorts": results}, ensure_ascii=False),
        encoding="utf-8",
    )
    progress.stage("encodage", 1.0)

    return JobResult(
        duration_in=info["duration"],
        duration_out=round(sum(r["duration"] for r in results), 3),
        cuts=cuts,
        language=(transcript or {}).get("language"),
        width=out_w,
        height=out_h,
        fps=fps,
        files=files,
        shorts=results,
    )
