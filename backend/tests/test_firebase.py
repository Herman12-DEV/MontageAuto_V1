"""Intégration Firebase : jetons d'identité, création de compte, montage depuis Storage, CRUD."""

from __future__ import annotations

import base64
import json
import time
from urllib.parse import quote

import pytest

from app import firebase, worker
from app.config import settings
from app.db import SessionLocal
from app.models import Project, User
from tests.conftest import make_video, needs_ffmpeg

PROJECT = "demo-autocut"
BUCKET = "demo-autocut.appspot.com"


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def emulator_token(uid: str, email: str, **claims) -> str:
    """Jeton au format de l'émulateur Firebase Auth (non signé)."""
    body = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "user_id": uid,
        "sub": uid,
        "email": email,
        "exp": int(time.time()) + 3600,
        **claims,
    }
    return f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(body)}."


@pytest.fixture
def emulator(monkeypatch):
    monkeypatch.setattr(settings, "firebase_project_id", PROJECT)
    monkeypatch.setattr(settings, "firebase_storage_bucket", BUCKET)
    monkeypatch.setattr(settings, "firebase_auth_emulator_host", "127.0.0.1:9099")
    monkeypatch.setattr(settings, "firebase_storage_emulator_host", "127.0.0.1:9199")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_first_login_creates_account_from_username(client, emulator):
    token = emulator_token("uid-1", "awa.kone@users.autocut.invalid")
    me = client.get("/api/me", headers=auth(token))
    assert me.status_code == 200, me.text
    data = me.json()
    assert data["username"] == "awa.kone" and data["email"] is None
    assert data["quota"]["remaining"] == 2
    # Deuxième connexion : même compte, pas de doublon.
    assert client.get("/api/me", headers=auth(token)).json()["id"] == data["id"]
    with SessionLocal() as db:
        assert db.query(User).count() == 1


def test_real_email_is_kept_and_verified_email_links_existing_account(client, emulator):
    with SessionLocal() as db:
        db.add(User(username="marc", email="marc@example.com", password_hash="x"))
        db.commit()
    unverified = emulator_token("uid-2", "marc@example.com", email_verified=False)
    data = client.get("/api/me", headers=auth(unverified)).json()
    assert data["username"] != "marc" and data["email"] is None  # pas de rattachement sans vérification
    verified = emulator_token("uid-3", "marc@example.com", email_verified=True, name="Marc")
    assert client.get("/api/me", headers=auth(verified)).json()["username"] == "marc"


def test_invalid_or_foreign_tokens_are_rejected(client, emulator):
    expired = emulator_token("uid-1", "a@users.autocut.invalid", exp=int(time.time()) - 10)
    assert client.get("/api/me", headers=auth(expired)).status_code == 401
    foreign = emulator_token("uid-1", "a@users.autocut.invalid", aud="autre-projet")
    assert client.get("/api/me", headers=auth(foreign)).status_code == 401


def test_unsigned_tokens_refused_outside_emulator(client, monkeypatch):
    monkeypatch.setattr(settings, "firebase_project_id", PROJECT)
    monkeypatch.setattr(settings, "firebase_auth_emulator_host", "")
    token = emulator_token("uid-1", "a@users.autocut.invalid")
    assert client.get("/api/me", headers=auth(token)).status_code == 401


def _storage_url(path: str, host: str = "127.0.0.1:9199", scheme: str = "http") -> str:
    return f"{scheme}://{host}/v0/b/{BUCKET}/o/{quote(path, safe='')}?alt=media&token=abc"


def test_storage_source_must_belong_to_user(emulator):
    path = "users/uid-1/sources/clip.mp4"
    firebase.validate_storage_source("uid-1", path, _storage_url(path))
    with pytest.raises(firebase.FirebaseError):
        firebase.validate_storage_source("uid-2", path, _storage_url(path))
    with pytest.raises(firebase.FirebaseError):
        firebase.validate_storage_source("uid-1", path, _storage_url(path, host="evil.example.com"))
    with pytest.raises(firebase.FirebaseError):
        firebase.validate_storage_source("uid-1", "users/uid-1/../uid-2/x.mp4", _storage_url(path))


@needs_ffmpeg
def test_project_from_storage_full_crud(client, emulator, tmp_path, monkeypatch):
    token = emulator_token("uid-9", "zoe@users.autocut.invalid")
    headers = auth(token)
    video = make_video(tmp_path / "clip.mp4", [("tone", 1.0), ("silence", 1.5), ("tone", 1.0)])
    path = "users/uid-9/sources/1-clip.mp4"

    # Le worker « télécharge » depuis le Storage : on simule la réponse du bucket.
    def fake_download(url, target, max_bytes, on_progress=None):
        assert url == _storage_url(path)
        target.write_bytes(video.read_bytes())
        return target

    monkeypatch.setattr(firebase, "download", fake_download)

    # Create
    res = client.post(
        "/api/projects",
        json={
            "storage": {"path": path, "url": _storage_url(path), "filename": "clip.mp4", "size": video.stat().st_size},
            "options": {"subtitles": False},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    project = res.json()
    assert project["source_kind"] == "storage" and project["storage_path"] == path
    assert worker.claim_next("t") == project["id"]
    worker.process(project["id"])

    # Read
    detail = client.get(f"/api/projects/{project['id']}", headers=headers).json()
    assert detail["status"] == "done" and detail["cuts"] == 1
    assert [p["id"] for p in client.get("/api/projects", headers=headers).json()["projects"]] == [project["id"]]

    # Update (renommer)
    res = client.patch(f"/api/projects/{project['id']}", json={"title": "Mon interview"}, headers=headers)
    assert res.status_code == 200 and res.json()["title"] == "Mon interview"
    assert client.patch(f"/api/projects/{project['id']}", json={"title": ""}, headers=headers).status_code == 422

    # Un autre utilisateur ne voit ni ne modifie ce montage.
    other = auth(emulator_token("uid-10", "eve@users.autocut.invalid"))
    assert client.get(f"/api/projects/{project['id']}", headers=other).status_code == 404
    assert client.patch(f"/api/projects/{project['id']}", json={"title": "x"}, headers=other).status_code == 404

    # Delete
    assert client.delete(f"/api/projects/{project['id']}", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.get(Project, project["id"]) is None


def test_storage_project_rejects_foreign_file(client, emulator):
    headers = auth(emulator_token("uid-9", "zoe@users.autocut.invalid"))
    path = "users/uid-OTHER/sources/clip.mp4"
    res = client.post(
        "/api/projects",
        json={"storage": {"path": path, "url": _storage_url(path), "filename": "clip.mp4", "size": 1000}},
        headers=headers,
    )
    assert res.status_code == 422 and res.json()["detail"]["code"] == "bad_storage"
