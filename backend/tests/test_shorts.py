"""Shorts : choix des extraits, conversion vers la source, rendu et API."""

from __future__ import annotations

import json
import subprocess

from app.engine import ffmpeg, pipeline, shorts
from app.config import settings
from app.db import SessionLocal
from app.models import Project
from app import worker
from tests.conftest import needs_ffmpeg, register_and_login
import itertools


def _phrases(spec):
    """spec = [(début, fin, nb_mots)] → phrases au format transcript."""
    phrases = []
    for start, end, n in spec:
        step = (end - start) / n
        phrases.append({"words": [{"w": f"m{i}", "s": start + i * step, "e": start + (i + 1) * step} for i in range(n)]})
    return phrases


def test_clamp_limits():
    assert shorts.clamp(0, 0) == (3, 30)
    assert shorts.clamp(50, 999) == (10, 150)
    assert shorts.clamp(2, 10) == (2, 30)
    assert shorts.clamp(4, 95.7) == (4, 95)


def test_normalize_options_defaults_to_three_shorts_of_30s():
    opts = pipeline.normalize_options({"mode": "shorts"})
    assert (opts["mode"], opts["shorts_count"], opts["shorts_duration"]) == ("shorts", 3, 30)
    assert pipeline.normalize_options({"mode": "???"})["mode"] == "full"


def test_windows_follow_phrases_and_prefer_dense_speech():
    # 0-60 s : parole lente ; 60-120 s : parole dense ; 120-180 s : parole lente.
    spec = [(t, t + 9, 10) for t in range(0, 60, 10)]
    spec += [(t, t + 9, 30) for t in range(60, 120, 10)]
    spec += [(t, t + 9, 10) for t in range(120, 180, 10)]
    windows = shorts.select_windows(_phrases(spec), 180, 1, 30)
    assert len(windows) == 1
    start, end = windows[0]
    assert 59 <= start <= 61 and end - start <= 30
    assert end - start >= 18  # se termine à la fin d'une phrase, sans dépasser 30 s


def test_windows_never_overlap_and_respect_count_and_length():
    spec = [(t, t + 4, 8) for t in range(0, 300, 5)]
    windows = shorts.select_windows(_phrases(spec), 300, 5, 45)
    assert len(windows) == 5
    for (_s1, e1), (s2, _e2) in itertools.pairwise(windows):
        assert e1 <= s2
    assert all(e - s <= 45 for s, e in windows)


def test_short_video_gives_single_short():
    assert shorts.select_windows([], 20, 3, 30) == [(0.0, 20.0)]


def test_without_transcript_windows_are_evenly_spaced():
    windows = shorts.select_windows([], 120, 3, 30)
    assert len(windows) == 3
    assert windows[0][0] == 0 and windows[-1][1] <= 120


def test_source_segments_maps_cut_timeline_to_source():
    kept = [(10.0, 20.0), (30.0, 40.0), (50.0, 60.0)]  # timeline coupée : 0-10, 10-20, 20-30
    assert shorts.source_segments(kept, (5.0, 25.0)) == [(15.0, 20.0), (30.0, 40.0), (50.0, 55.0)]


def test_words_in_window_are_shifted():
    words = [{"w": "a", "s": 9.0, "e": 9.5}, {"w": "b", "s": 10.2, "e": 10.6}, {"w": "c", "s": 25.0, "e": 25.4}]
    assert shorts.words_in_window(words, (10.0, 20.0)) == [{"w": "b", "s": 0.2, "e": 0.6}]


def _talking_video(path, seconds):
    subprocess.run(
        [
            ffmpeg.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=25:duration={seconds}",
            "-f", "lavfi", "-i", f"aevalsrc='0.5*sin(2*PI*440*t)*lt(mod(t,4),3)':s=48000:d={seconds}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(path),
        ],
        check=True,
    )


def _durations(path):
    out = subprocess.run(
        [ffmpeg.ffprobe_bin(), "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return {s["codec_type"]: float(s["duration"]) for s in json.loads(out)["streams"]}


@needs_ffmpeg
def test_pipeline_renders_requested_shorts(tmp_path):
    _talking_video(tmp_path / "source.mp4", 120)
    result = pipeline.run(
        tmp_path,
        {"mode": "shorts", "shorts_count": 3, "shorts_duration": 30, "subtitles": False, "format": "9:16"},
        watermark="AutoCut",
        report=lambda *_: None,
    )
    assert len(result.shorts) == 3
    assert not (tmp_path / "output.mp4").exists()
    for item in result.shorts:
        d = _durations(tmp_path / item["video"])
        assert d["video"] <= 30.05 and d["video"] >= 20
        assert abs(d["video"] - d["audio"]) < 0.1
    # Nouveau rendu (changement de format) : mêmes extraits, réutilisés.
    again = pipeline.run(
        tmp_path,
        {"mode": "shorts", "shorts_count": 3, "shorts_duration": 30, "subtitles": False, "format": "1:1"},
        watermark=None,
        report=lambda *_: None,
        rerender=True,
    )
    assert [(s["start"], s["end"]) for s in again.shorts] == [(s["start"], s["end"]) for s in result.shorts]
    assert (again.width, again.height) == (720, 720)


@needs_ffmpeg
def test_shorts_end_to_end_through_api(client, tmp_path):
    headers = register_and_login(client)
    _talking_video(tmp_path / "clip.mp4", 75)
    data = (tmp_path / "clip.mp4").read_bytes()
    up = client.post("/api/uploads", json={"filename": "clip.mp4", "size": len(data)}, headers=headers).json()
    client.put(
        f"/api/uploads/{up['upload_id']}?offset=0", content=data,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    client.post(f"/api/uploads/{up['upload_id']}/complete", headers=headers)
    res = client.post(
        "/api/projects",
        json={"upload_id": up["upload_id"], "options": {"mode": "shorts", "shorts_count": 2, "shorts_duration": 30, "subtitles": False}},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    pid = res.json()["id"]
    assert worker.claim_next("t") == pid
    worker.process(pid)
    detail = client.get(f"/api/projects/{pid}", headers=headers).json()
    assert detail["status"] == "done" and detail["mode"] == "shorts"
    assert len(detail["media"]["shorts"]) == 2 and "video" not in detail["media"]
    first = detail["media"]["shorts"][0]
    video = client.get(first["video_download"])
    assert video.status_code == 200 and "-short-1.mp4" in video.headers["content-disposition"]
    assert client.get(f"/api/files/{pid}/short-1").status_code == 404  # jeton obligatoire
    assert client.get(f"/api/files/{pid}/short-99?token=x").status_code == 404

    # Passer à 1 short de 45 s sans crédit supplémentaire.
    res = client.post(f"/api/projects/{pid}/rerender", json={"options": {"shorts_count": 1, "shorts_duration": 45}}, headers=headers)
    assert res.status_code == 200
    assert worker.claim_next("t") == pid
    worker.process(pid)
    detail = client.get(f"/api/projects/{pid}", headers=headers).json()
    assert len(detail["media"]["shorts"]) == 1
    assert client.get("/api/me", headers=headers).json()["quota"]["used"] == 1
    with SessionLocal() as db:
        assert db.get(Project, pid).options["shorts_duration"] == 45
    assert not (settings.projects_dir / pid / "short_2.mp4").exists()
