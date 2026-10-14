"""File d'attente, reprise après coupure (R10), remboursement (F-TRT-06), purge (§8.3)."""

from __future__ import annotations

from datetime import timedelta

from app import worker
from app.config import settings
from app.db import SessionLocal
from app.engine import EngineError, pipeline
from app.models import Project, User, utcnow
from tests.conftest import make_video, needs_ffmpeg, register_and_login, sent_subjects


def _user() -> str:
    with SessionLocal() as db:
        user = User(username="w", password_hash="x", credits_period=utcnow().strftime("%Y-%m"), credits_used=1)
        db.add(user)
        db.commit()
        return user.id


def _project(user_id: str, **kw) -> str:
    with SessionLocal() as db:
        project = Project(
            user_id=user_id,
            title=kw.pop("title", "Test"),
            options={"subtitles": False},
            expires_at=kw.pop("expires_at", utcnow() + timedelta(days=30)),
            credit_charged=True,
            **kw,
        )
        db.add(project)
        db.commit()
        (settings.projects_dir / project.id).mkdir(parents=True, exist_ok=True)
        return project.id


def test_claim_respects_priority_and_is_exclusive():
    uid = _user()
    low = _project(uid, priority=0)
    high = _project(uid, priority=10)
    assert worker.claim_next("w1") == high
    assert worker.claim_next("w2") == low
    assert worker.claim_next("w3") is None


def test_r10_stale_jobs_are_requeued_then_failed_with_refund():
    uid = _user()
    pid = _project(uid, status="processing", attempts=1, heartbeat_at=utcnow() - timedelta(hours=1))
    worker.requeue_stale()
    with SessionLocal() as db:
        assert db.get(Project, pid).status == "queued"
        project = db.get(Project, pid)
        project.status, project.attempts = "processing", 2
        project.heartbeat_at = utcnow() - timedelta(hours=1)
        db.commit()
    worker.requeue_stale()
    with SessionLocal() as db:
        project = db.get(Project, pid)
        assert project.status == "failed"
        assert db.get(User, uid).credits_used == 0  # crédit rendu


def test_failed_job_refunds_credit(monkeypatch):
    uid = _user()
    pid = _project(uid)
    assert worker.claim_next("w") == pid

    def boom(*args, **kwargs):
        raise EngineError("Ce fichier ne contient aucune piste vidéo.")

    monkeypatch.setattr(pipeline, "run", boom)
    worker.process(pid)
    with SessionLocal() as db:
        project = db.get(Project, pid)
        assert project.status == "failed"
        assert project.error == "Ce fichier ne contient aucune piste vidéo."
        assert project.credit_charged is False
        assert db.get(User, uid).credits_used == 0


def test_purge_removes_expired_projects_and_files():
    uid = _user()
    old = _project(uid, status="done", expires_at=utcnow() - timedelta(days=1))
    fresh = _project(uid, status="done")
    worker.purge_expired()
    with SessionLocal() as db:
        assert db.get(Project, old) is None
        assert db.get(Project, fresh) is not None
    assert not (settings.projects_dir / old).exists()
    assert (settings.projects_dir / fresh).exists()


@needs_ffmpeg
def test_end_to_end_through_api_and_worker(client, tmp_path):
    """R2/R3/R6 : dépôt → file → worker → aperçu, téléchargement, statistiques."""
    headers = register_and_login(client, email="awa@example.com")
    client.patch("/api/me", json={"prefs": {"notify_email": True}}, headers=headers)
    video = make_video(tmp_path / "clip.mp4", [("tone", 1.0), ("silence", 1.5), ("tone", 1.0)])
    data = video.read_bytes()
    up = client.post("/api/uploads", json={"filename": "clip.mp4", "size": len(data)}, headers=headers).json()
    client.put(
        f"/api/uploads/{up['upload_id']}?offset=0",
        content=data,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert client.post(f"/api/uploads/{up['upload_id']}/complete", headers=headers).status_code == 200
    res = client.post(
        "/api/projects",
        json={"upload_id": up["upload_id"], "title": "Interview client", "options": {"subtitles": False, "format": "1:1"}},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    project = res.json()
    assert project["status"] == "queued" and project["queue_position"] == 1
    assert client.get("/api/me", headers=headers).json()["quota"]["remaining"] == 1

    assert worker.claim_next("test") == project["id"]
    worker.process(project["id"])

    detail = client.get(f"/api/projects/{project['id']}", headers=headers).json()
    assert detail["status"] == "done", detail
    assert detail["cuts"] == 1
    assert detail["saved_pct"] > 30
    assert (detail["width"], detail["height"]) == (720, 720)
    res = client.get(detail["media"]["video_download"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    assert "interview-client.mp4" in res.headers["content-disposition"]
    # Lecture partielle (Range) indispensable au lecteur vidéo du navigateur.
    partial = client.get(detail["media"]["video"], headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206 and len(partial.content) == 100
    assert any("Votre montage est prêt" in s for s in sent_subjects())  # notification F-TRT-03

    # Rendu cosmétique (changement de format) : sans crédit supplémentaire.
    res = client.post(f"/api/projects/{project['id']}/rerender", json={"options": {"format": "9:16"}}, headers=headers)
    assert res.status_code == 200 and res.json()["status"] == "queued"
    assert worker.claim_next("test") == project["id"]
    worker.process(project["id"])
    detail = client.get(f"/api/projects/{project['id']}", headers=headers).json()
    assert detail["status"] == "done" and detail["height"] == 1280
    assert client.get("/api/me", headers=headers).json()["quota"]["remaining"] == 1


def test_worker_stays_online_during_a_long_job(client, monkeypatch):
    """Régression : pendant un montage, l'indicateur « Moteur IA » passait à « indisponible »."""
    import threading
    import time

    from app.db import SessionLocal
    from app.models import WorkerHeartbeat

    uid = _user()
    pid = _project(uid, status="processing", heartbeat_at=utcnow())
    with SessionLocal() as db:
        db.query(WorkerHeartbeat).delete()
        db.commit()
    monkeypatch.setattr(worker, "HEARTBEAT_EVERY", 0.05)
    stop = threading.Event()
    thread = threading.Thread(target=worker._heartbeat_loop, args=(pid, stop, "w-test"))
    thread.start()
    time.sleep(0.3)
    stop.set()
    thread.join()
    assert client.get("/api/health").json()["workers"] == 1
