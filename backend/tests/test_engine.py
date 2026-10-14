"""Tests d'intégration du moteur avec un vrai FFmpeg (sans Whisper : sous-titres désactivés)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import music
from app.engine import EngineError, ffmpeg, pipeline, render
from tests.conftest import make_video, needs_ffmpeg

PATTERN = [("tone", 1.0), ("silence", 1.5), ("tone", 1.0), ("silence", 2.0), ("tone", 1.0)]


def _durations(path: Path) -> tuple[float, float]:
    import json
    import subprocess

    out = subprocess.run(
        [ffmpeg.ffprobe_bin(), "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    streams = {s["codec_type"]: float(s["duration"]) for s in json.loads(out)["streams"]}
    return streams["video"], streams["audio"]


def test_output_sizes():
    assert render.output_size("9:16", 1920, 1080) == (1080, 1920)
    assert render.output_size("9:16", 1280, 720) == (720, 1280)
    assert render.output_size("1:1", 3840, 2160) == (1080, 1080)
    assert render.output_size("original", 3840, 2160) == (1920, 1080)
    assert render.output_size("original", 1080, 1920) == (1080, 1920)
    assert render.output_size("original", 853, 480) == (852, 480)


def test_normalize_options_clamps_values():
    opts = pipeline.normalize_options(
        {"silence_db": -200, "padding_ms": 99999, "format": "4:3", "language": "de", "subtitle_style": "?", "x": 1}
    )
    assert opts["silence_db"] == -70.0
    assert opts["padding_ms"] == 1000
    assert opts["format"] == "9:16"
    assert opts["language"] == "auto"
    assert opts["subtitle_style"] == "karaoke"
    assert "x" not in opts


@needs_ffmpeg
def test_probe_rejects_non_video(tmp_path):
    fake = tmp_path / "virus.mp4"
    fake.write_bytes(b"MZ\x90\x00" + os.urandom(2048))
    with pytest.raises(EngineError):
        ffmpeg.probe(fake)


@needs_ffmpeg
def test_pipeline_removes_silences_and_keeps_sync(tmp_path):
    make_video(tmp_path / "source.mp4", PATTERN)
    stages = []
    result = pipeline.run(
        tmp_path,
        {"subtitles": False, "format": "9:16"},
        watermark="AutoCut",
        report=lambda stage, p: stages.append(stage),
    )
    assert result.cuts == 2
    assert 3.1 <= result.duration_out <= 3.8, result.duration_out
    assert (result.width, result.height) == (720, 1280)
    assert stages[0] == "analyse" and stages[-1] == "encodage"
    video, audio = _durations(tmp_path / "output.mp4")
    assert abs(video - result.duration_out) < 0.05
    assert abs(audio - video) < 0.05
    assert (tmp_path / "render.ass").exists()  # filigrane


@needs_ffmpeg
def test_pipeline_handles_many_cuts(tmp_path):
    """Régression : au-delà de 100 plages, FFmpeg refusait l'expression de sélection
    (« Cannot allocate memory ») — cas typique d'une interview YouTube de 20 min."""
    import subprocess

    count = 150
    subprocess.run(
        [
            ffmpeg.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=25:duration={count * 0.9}",
            "-f", "lavfi", "-i", f"aevalsrc='0.5*sin(2*PI*440*t)*lt(mod(t,0.9),0.3)':s=48000:d={count * 0.9}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(tmp_path / "source.mp4"),
        ],
        check=True,
    )
    result = pipeline.run(tmp_path, {"subtitles": False, "format": "original"}, watermark=None, report=lambda *_: None)
    assert result.cuts >= 140
    video, audio = _durations(tmp_path / "output.mp4")
    assert abs(video - result.duration_out) < 0.1
    assert abs(audio - video) < 0.1


@needs_ffmpeg
def test_pipeline_with_music_and_original_format(tmp_path):
    tracks = music.list_tracks()
    if not tracks:
        pytest.skip("Bibliothèque musicale non générée")
    make_video(tmp_path / "source.mp4", PATTERN, size="320x240")
    result = pipeline.run(
        tmp_path,
        {"subtitles": False, "format": "original", "music": tracks[0]["id"], "cut_silences": False},
        watermark=None,
        report=lambda *_: None,
    )
    assert result.cuts == 0
    assert abs(result.duration_out - 6.5) < 0.05
    assert (result.width, result.height) == (320, 240)
    assert not (tmp_path / "render.ass").exists()


@needs_ffmpeg
@pytest.mark.skipif(os.getenv("RUN_WHISPER_TESTS") != "1", reason="RUN_WHISPER_TESTS=1 pour tester Whisper")
def test_pipeline_transcribes_speech(tmp_path):
    sample = os.getenv("WHISPER_SAMPLE_VIDEO")
    if not sample:
        pytest.skip("WHISPER_SAMPLE_VIDEO non défini")
    (tmp_path / "source.mp4").write_bytes(Path(sample).read_bytes())
    result = pipeline.run(tmp_path, {"subtitles": True}, watermark=None, report=lambda *_: None)
    assert result.language in ("fr", "en")
    assert pipeline.flat_words(pipeline.load_transcript(tmp_path))
    assert (tmp_path / "subtitles.srt").read_text(encoding="utf-8").strip()
