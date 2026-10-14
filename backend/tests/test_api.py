"""Tests de l'API, calqués sur les scénarios de recette du cahier des charges (§10)."""

from __future__ import annotations

import os

from app import ratelimit
from app.config import settings
from app.db import SessionLocal
from app.models import Project, User
from tests.conftest import last_email_link, make_video, needs_ffmpeg, register_and_login, sent_subjects


def _upload(client, headers, path, chunk=None):
    data = path.read_bytes()
    res = client.post("/api/uploads", json={"filename": path.name, "size": len(data)}, headers=headers)
    assert res.status_code == 201, res.text
    upload = res.json()
    size = chunk or upload["chunk_size"]
    for offset in range(0, len(data), size):
        res = client.put(
            f"/api/uploads/{upload['upload_id']}?offset={offset}",
            content=data[offset : offset + size],
            headers={**headers, "Content-Type": "application/octet-stream"},
        )
        assert res.status_code == 200, res.text
    return client.post(f"/api/uploads/{upload['upload_id']}/complete", headers=headers)


# --- R1 : inscription immédiate, connexion par nom d'utilisateur ------------------


def test_r1_register_logs_in_immediately_with_two_free_credits(client):
    res = client.post("/api/auth/register", json={"username": "Awa.Kone", "password": "motdepasse1"})
    assert res.status_code == 201
    body = res.json()
    assert body["access_token"] and body["created"] is True
    assert body["user"]["username"] == "awa.kone" and body["user"]["email"] is None
    quota = body["user"]["quota"]
    assert quota["plan"] == "free" and quota["remaining"] == 2 and quota["limit"] == 2
    me = client.get("/api/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["username"] == "awa.kone"
    assert not list(settings.outbox_dir.glob("*.eml"))  # aucun e-mail de confirmation

    # Reconnexion avec ses accès (insensible à la casse du nom d'utilisateur).
    res = client.post("/api/auth/login", json={"identifier": "AWA.KONE", "password": "motdepasse1"})
    assert res.status_code == 200 and res.json()["user"]["username"] == "awa.kone"


def test_login_with_email_once_added(client):
    register_and_login(client, "awa", email="awa@example.com")
    res = client.post("/api/auth/login", json={"identifier": "Awa@Example.com", "password": "motdepasse1"})
    assert res.status_code == 200


def test_passwords_are_hashed(client):
    register_and_login(client)
    with SessionLocal() as db:
        user = db.query(User).one()
        assert "motdepasse1" not in user.password_hash
        assert user.password_hash.startswith("$2")


def test_username_rules_duplicates_and_bad_password(client):
    register_and_login(client, "awa")
    res = client.post("/api/auth/register", json={"username": "AWA", "password": "autrechose"})
    assert res.status_code == 409 and res.json()["detail"]["code"] == "username_taken"
    res = client.post("/api/auth/register", json={"username": "a b", "password": "autrechose"})
    assert res.status_code == 422 and res.json()["detail"]["code"] == "bad_username"
    res = client.post("/api/auth/login", json={"identifier": "awa", "password": "mauvais!!"})
    assert res.status_code == 401
    res = client.post("/api/auth/register", json={"username": "xavier", "password": "court"})
    assert res.status_code == 422
    assert "8 caractères" in res.json()["detail"]["message"]


def test_password_reset_needs_an_email_and_invalidates_old_sessions(client):
    headers = register_and_login(client, "awa", email="awa@example.com")
    assert client.post("/api/auth/forgot", json={"identifier": "awa"}).status_code == 200
    token = last_email_link("reinitialiser")
    res = client.post("/api/auth/reset", json={"token": token, "password": "nouveaumdp1"})
    assert res.status_code == 200
    assert client.get("/api/me", headers=headers).status_code == 401  # ancienne session
    # Le lien ne sert qu'une fois.
    assert client.post("/api/auth/reset", json={"token": token, "password": "encoreun1"}).status_code == 400
    res = client.post("/api/auth/login", json={"identifier": "awa", "password": "nouveaumdp1"})
    assert res.status_code == 200


def test_login_rate_limited(client):
    ratelimit.reset()
    codes = [
        client.post("/api/auth/login", json={"identifier": "zoe", "password": "abcdefgh"}).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [401] * 10
    assert codes[-1] == 429


def test_google_login_creates_then_reuses_account(client, monkeypatch):
    from app.routers import auth as auth_router

    assert client.get("/api/auth/config").json() == {"google_client_id": None}
    res = client.post("/api/auth/google", json={"credential": "x" * 20})
    assert res.status_code == 503  # non configuré

    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    claims = {
        "iss": "accounts.google.com",
        "sub": "g-123",
        "email": "Awa.Kone@gmail.com",
        "email_verified": True,
        "name": "Awa Koné",
    }
    monkeypatch.setattr(auth_router, "_verify_google", lambda credential: claims)
    first = client.post("/api/auth/google", json={"credential": "jeton-google-valide"})
    assert first.status_code == 200 and first.json()["created"] is True
    user = first.json()["user"]
    assert user["username"] == "awa.kone" and user["email"] == "awa.kone@gmail.com"
    assert user["google_linked"] and not user["has_password"]
    again = client.post("/api/auth/google", json={"credential": "jeton-google-valide"})
    assert again.json()["created"] is False and again.json()["user"]["id"] == user["id"]
    # Pas de mot de passe : la connexion par identifiants renvoie vers Google.
    res = client.post("/api/auth/login", json={"identifier": "awa.kone", "password": "nimportequoi"})
    assert res.json()["detail"]["code"] == "use_google"


def test_google_links_existing_account_with_same_email(client, monkeypatch):
    from app.routers import auth as auth_router

    register_and_login(client, "marc", email="marc@example.com")
    monkeypatch.setattr(settings, "google_client_id", "id")
    monkeypatch.setattr(
        auth_router,
        "_verify_google",
        lambda c: {"iss": "accounts.google.com", "sub": "g-9", "email": "marc@example.com", "email_verified": True},
    )
    res = client.post("/api/auth/google", json={"credential": "jeton-google-valide"})
    assert res.json()["created"] is False and res.json()["user"]["username"] == "marc"
    with SessionLocal() as db:
        assert db.query(User).count() == 1


def test_profile_update_and_prefs(client):
    headers = register_and_login(client)
    res = client.patch(
        "/api/me",
        json={"name": "Awa K.", "prefs": {"subtitle_style": "jaune", "notify_email": False}},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Awa K."
    assert data["prefs"]["subtitle_style"] == "jaune" and data["prefs"]["notify_email"] is False
    assert data["prefs"]["format"] == "9:16"  # valeur par défaut conservée
    bad = client.patch("/api/me", json={"prefs": {"subtitle_style": "inconnu"}}, headers=headers)
    assert bad.status_code == 422


# --- Import ----------------------------------------------------------------------


def test_upload_rejects_bad_extension_and_size(client):
    headers = register_and_login(client)
    res = client.post("/api/uploads", json={"filename": "film.avi", "size": 100}, headers=headers)
    assert res.status_code == 422
    big = settings.max_upload_bytes + 1
    res = client.post("/api/uploads", json={"filename": "film.mp4", "size": big}, headers=headers)
    assert res.status_code == 413


def test_r9_renamed_exe_is_rejected_cleanly(client, tmp_path):
    headers = register_and_login(client)
    fake = tmp_path / "video.mp4"
    fake.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00" + os.urandom(4096))
    res = client.post("/api/uploads", json={"filename": "video.mp4", "size": fake.stat().st_size}, headers=headers)
    upload_id = res.json()["upload_id"]
    res = client.put(
        f"/api/uploads/{upload_id}?offset=0",
        content=fake.read_bytes(),
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert res.status_code == 422
    assert "Format non pris en charge" in res.json()["detail"]["message"]
    assert not list(settings.uploads_dir.iterdir())  # fichier supprimé


@needs_ffmpeg
def test_upload_resume_after_interruption(client, tmp_path):
    headers = register_and_login(client)
    video = make_video(tmp_path / "clip.mp4", [("tone", 1.0)])
    data = video.read_bytes()
    res = client.post("/api/uploads", json={"filename": "clip.mp4", "size": len(data)}, headers=headers)
    upload_id = res.json()["upload_id"]
    half = len(data) // 2
    octet = {**headers, "Content-Type": "application/octet-stream"}
    client.put(f"/api/uploads/{upload_id}?offset=0", content=data[:half], headers=octet)
    # Mauvais décalage : le serveur indique où reprendre.
    res = client.put(f"/api/uploads/{upload_id}?offset=10", content=data[half:], headers=octet)
    assert res.status_code == 409 and res.json()["detail"]["received"] == half
    assert client.get(f"/api/uploads/{upload_id}", headers=headers).json()["received"] == half
    client.put(f"/api/uploads/{upload_id}?offset={half}", content=data[half:], headers=octet)
    res = client.post(f"/api/uploads/{upload_id}/complete", headers=headers)
    assert res.status_code == 200
    assert res.json()["probe"]["duration"] > 0.9


# --- Montages et quotas -------------------------------------------------------------


@needs_ffmpeg
def test_r7_quota_exceeded_after_two_free_videos(client, tmp_path):
    headers = register_and_login(client)
    video = make_video(tmp_path / "clip.mp4", [("tone", 1.0)])
    for _i in range(2):
        upload = _upload(client, headers, video).json()
        res = client.post("/api/projects", json={"upload_id": upload["upload_id"]}, headers=headers)
        assert res.status_code == 201, res.text
        # Libère le créneau « 1 montage actif » de l'offre gratuite.
        with SessionLocal() as db:
            db.get(Project, res.json()["id"]).status = "done"
            db.commit()
    upload = _upload(client, headers, video).json()
    res = client.post("/api/projects", json={"upload_id": upload["upload_id"]}, headers=headers)
    assert res.status_code == 402
    assert res.json()["detail"]["code"] == "quota_exceeded"
    with SessionLocal() as db:
        assert db.query(Project).count() == 2  # aucun traitement fantôme


@needs_ffmpeg
def test_free_plan_rejects_videos_longer_than_five_minutes(client, tmp_path):
    headers = register_and_login(client)
    video = make_video(tmp_path / "clip.mp4", [("tone", 1.0)])
    upload = _upload(client, headers, video).json()
    with SessionLocal() as db:
        from app.models import Upload

        db.get(Upload, upload["upload_id"]).probe = {**upload["probe"], "duration": 6 * 60}
        db.commit()
    res = client.post("/api/projects", json={"upload_id": upload["upload_id"]}, headers=headers)
    assert res.status_code == 422 and res.json()["detail"]["code"] == "too_long"


@needs_ffmpeg
def test_nf_sec_02_videos_are_private(client, tmp_path):
    owner = register_and_login(client, "awa")
    other = register_and_login(client, "marc")
    video = make_video(tmp_path / "clip.mp4", [("tone", 1.0)])
    upload = _upload(client, owner, video).json()
    project = client.post("/api/projects", json={"upload_id": upload["upload_id"]}, headers=owner).json()
    assert client.get(f"/api/projects/{project['id']}", headers=other).status_code == 404
    (settings.projects_dir / project["id"] / "output.mp4").write_bytes(b"fake")
    detail = client.get(f"/api/projects/{project['id']}", headers=owner).json()
    assert client.get(detail["media"]["video"]).status_code == 200
    assert client.get(f"/api/files/{project['id']}/video").status_code == 404
    assert client.get(f"/api/files/{project['id']}/video", headers=other).status_code == 404
    listing = client.get("/api/projects", headers=other).json()
    assert listing["projects"] == []


def test_r8_fake_payment_activates_pro_immediately(client):
    headers = register_and_login(client, email="awa@example.com")
    res = client.post("/api/billing/checkout", json={"plan": "pro"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["activated"] is True
    quota = client.get("/api/me", headers=headers).json()["quota"]
    assert quota["plan"] == "pro" and quota["unlimited"] is True and quota["watermark"] is False
    assert any("Merci pour votre abonnement" in s for s in sent_subjects())  # reçu par e-mail


def test_delete_account_removes_everything(client):
    headers = register_and_login(client)
    res = client.request("DELETE", "/api/me", json={"password": "faux-mot-de-passe"}, headers=headers)
    assert res.status_code == 400
    res = client.request("DELETE", "/api/me", json={"password": "motdepasse1"}, headers=headers)
    assert res.status_code == 200
    with SessionLocal() as db:
        assert db.query(User).count() == 0
    assert client.get("/api/me", headers=headers).status_code == 401


def test_library_and_health(client):
    lib = client.get("/api/library").json()
    assert len(lib["styles"]) >= 5
    assert {f["key"] for f in lib["formats"]} == {"9:16", "1:1", "original"}
    health = client.get("/api/health").json()
    assert "queue" in health and "ffmpeg" in health
