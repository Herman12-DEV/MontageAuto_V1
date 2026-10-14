"""Construction des graphes de filtres FFmpeg : coupe, recadrage, musique + ducking, incrustation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..config import settings
from . import ffmpeg
from .silences import Segment, or_expr, video_select_expr

AUDIO_RATE = 48000
# Taille des blocs audio : 80 échantillons à 48 kHz divise exactement la durée d'une image
# à 24/25/30/50/60 i/s, donc les coupes audio tombent pile sur les coupes vidéo.
AUDIO_CHUNK = 80

FORMATS = {"9:16", "1:1", "original"}


def output_fps(source_fps: float) -> float:
    return min(60.0, source_fps or 30.0)


def output_size(fmt: str, width: int, height: int) -> tuple[int, int]:
    """Résolution de sortie, 1080p max (F-RES-02)."""
    short = min(width, height)
    if fmt == "9:16":
        return (1080, 1920) if short >= 1000 else (720, 1280)
    if fmt == "1:1":
        return (1080, 1080) if short >= 1000 else (720, 720)
    scale = min(1.0, 1920 / max(width, height), 1080 / min(width, height))
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


def _video_chain(fmt: str, out_w: int, out_h: int) -> str:
    if fmt == "9:16":
        crop = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)'"
    elif fmt == "1:1":
        crop = "crop='min(iw,ih)':'min(iw,ih)'"
    else:
        crop = ""
    scale = f"scale={out_w}:{out_h}:flags=lanczos,setsar=1"
    return f"{crop},{scale}" if crop else scale


def audio_select_expr(kept: list[Segment]) -> str:
    half = AUDIO_CHUNK / AUDIO_RATE / 2
    return or_expr([f"gte(t,{s - half:.6f})*lt(t,{e - half:.6f})" for s, e in kept])


def _cut_audio_chain(kept: list[Segment], source_duration: float) -> str:
    # apad : une piste audio plus courte que la vidéo est complétée par du silence,
    # sinon la fin du montage perdrait le son et les sous-titres se décaleraient.
    return (
        f"aresample={AUDIO_RATE},apad=whole_dur={source_duration:.3f},"
        f"asetnsamples=n={AUDIO_CHUNK}:p=0,"
        f"aselect='{audio_select_expr(kept)}',asetpts=N/SR/TB"
    )


def extract_cut_audio(
    source: Path, kept: list[Segment], source_duration: float, workdir: Path, out_name: str = "speech.wav"
) -> Path:
    """Audio coupé en 16 kHz mono pour Whisper : horodatages directement dans la timeline finale."""
    graph = (
        f"[0:a]{_cut_audio_chain(kept, source_duration)},aresample=16000,"
        "aformat=channel_layouts=mono[a]"
    )
    script = workdir / "filter_audio.txt"
    script.write_text(graph, encoding="utf-8")
    ffmpeg.run(
        [
            "-i",
            str(source),
            *ffmpeg.filter_script_args("-filter_complex", script),
            "-map",
            "[a]",
            "-c:a",
            "pcm_s16le",
            out_name,
        ],
        cwd=workdir,
    )
    return workdir / out_name


def render(
    *,
    source: Path,
    workdir: Path,
    kept: list[Segment],
    probe: dict,
    fmt: str,
    subtitles_file: str | None,
    music: Path | None,
    music_volume: float,
    out_name: str = "output.mp4",
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    fps = output_fps(probe["fps"])
    out_w, out_h = output_size(fmt, probe["width"], probe["height"])
    duration = sum(e - s for s, e in kept)

    video = (
        f"[0:v]fps={fps},select='{video_select_expr(kept, fps)}',setpts=N/FRAME_RATE/TB,"
        f"{_video_chain(fmt, out_w, out_h)}"
    )
    if subtitles_file:
        video += f",subtitles=filename={subtitles_file}"
    graph = [video + ",format=yuv420p[vout]"]

    inputs = ["-i", str(source)]
    stereo = f"aformat=sample_rates={AUDIO_RATE}:channel_layouts=stereo"
    if probe["has_audio"]:
        graph.append(f"[0:a]{_cut_audio_chain(kept, probe['duration'])},{stereo}[voice]")
    else:
        graph.append(f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=0:{duration:.3f}[voice]")

    if music is not None:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fade_start = max(0.0, duration - 1.5)
        graph.append(
            f"[1:a]{stereo},atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,volume={music_volume:.3f},"
            f"afade=t=in:d=0.8,afade=t=out:st={fade_start:.3f}:d=1.5[music]"
        )
        # Ducking (F-HAB-01) : la voix pilote un compresseur appliqué à la musique.
        graph.append("[voice]asplit=2[v_main][v_side]")
        graph.append(
            "[music][v_side]sidechaincompress=threshold=0.015:ratio=12:attack=15:release=400:"
            "makeup=1[ducked]"
        )
        graph.append(
            "[v_main][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]"
        )
    else:
        graph.append("[voice]anull[aout]")

    script = workdir / "filter_render.txt"
    script.write_text(";\n".join(graph), encoding="utf-8")
    ffmpeg.run(
        [
            *inputs,
            *ffmpeg.filter_script_args("-filter_complex", script),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            settings.x264_preset,
            "-crf",
            str(settings.x264_crf),
            "-profile:v",
            "high",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-t",
            f"{duration:.3f}",
            "-movflags",
            "+faststart",
            out_name,
        ],
        cwd=workdir,
        duration=duration,
        on_progress=on_progress,
    )
    return workdir / out_name
