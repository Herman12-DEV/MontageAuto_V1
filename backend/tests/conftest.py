"""Environnement de test isolé : base SQLite et stockage temporaires, worker désactivé."""

from __future__ import annotations

import email
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="autocut-tests-"))
os.environ.update(
    {
        "APP_ENV": "test",
        "STORAGE_DIR": str(_TMP / "storage"),
        "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
        "EMBEDDED_WORKER": "false",
        "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789",
        "SMTP_HOST": "",
        "STRIPE_SECRET_KEY": "",
        "DEV_FAKE_PAYMENTS": "true",
        "WHISPER_MODEL": "tiny",
        "PUBLIC_URL": "http://test.local",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app import ratelimit  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base, engine, init_db  # noqa: E402
from app.engine import ffmpeg  # noqa: E402
from app.main import app  # noqa: E402

HAS_FFMPEG = ffmpeg.available()
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg non installé")


@pytest.fixture(autouse=True)
def _clean_state():
    Base.metadata.drop_all(engine)
    init_db()
    for sub in ("projects", "uploads", "outbox"):
        shutil.rmtree(settings.storage_dir / sub, ignore_errors=True)
    settings.ensure_dirs()
    ratelimit.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def last_email_link(kind: str) -> str:
    """Jeton du dernier lien envoyé (confirmer / reinitialiser) depuis storage/outbox."""
    files = sorted(settings.outbox_dir.glob("*.eml"), key=lambda p: p.stat().st_mtime_ns)
    for path in reversed(files):
        raw = path.read_bytes().decode("utf-8", "replace")
        # Le corps texte peut être encodé en quoted-printable : on le décode.
        message = email.message_from_string(raw)
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                text = part.get_payload(decode=True).decode("utf-8")
                match = re.search(rf"/{kind}\?token=([\w.-]+)", text)
                if match:
                    return match.group(1)
    raise AssertionError(f"Aucun e-mail « {kind} » trouvé")


def sent_subjects() -> list[str]:
    from email.header import decode_header, make_header

    subjects = []
    for path in sorted(settings.outbox_dir.glob("*.eml"), key=lambda p: p.stat().st_mtime_ns):
        message = email.message_from_bytes(path.read_bytes())
        subjects.append(str(make_header(decode_header(message["Subject"]))))
    return subjects


def register_and_login(
    client: TestClient, username: str = "awa", password: str = "motdepasse1", email: str | None = None
) -> dict:
    """Inscription par nom d'utilisateur : la session est ouverte immédiatement."""
    res = client.post("/api/auth/register", json={"username": username, "password": password})
    assert res.status_code == 201, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    if email:
        assert client.patch("/api/me", json={"email": email}, headers=headers).status_code == 200
    return headers


def make_video(path: Path, pattern: list[tuple[str, float]], size: str = "640x360", fps: int = 25) -> Path:
    """Vidéo de test : alternance de « bip » (parole simulée) et de silences.

    pattern = [("tone", 1.0), ("silence", 1.2), ...]
    """
    parts = []
    for kind, dur in pattern:
        if kind == "tone":
            parts.append(f"sine=frequency=440:sample_rate=48000:duration={dur}")
        else:
            parts.append(f"anullsrc=r=48000:cl=mono,atrim=0:{dur}")
    total = sum(d for _, d in pattern)
    labels = "".join(f"[a{i}]" for i in range(len(parts)))
    graph = ";".join(f"{p}[a{i}]" for i, p in enumerate(parts))
    graph += f";{labels}concat=n={len(parts)}:v=0:a=1[aout]"
    subprocess.run(
        [
            ffmpeg.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}:duration={total}",
            "-filter_complex", graph,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
    )
    return path
