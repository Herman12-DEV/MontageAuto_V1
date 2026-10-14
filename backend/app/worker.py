"""Worker de traitement : prend les montages en file, les exécute, purge les données expirées.

La file est la table `projects` elle-même : la prise d'un job est une mise à jour
conditionnelle atomique (`status = 'queued'`), ce qui permet de lancer autant de workers
que nécessaire, sur une ou plusieurs machines (NF-SCA-01). Un job dont le worker s'est
arrêté (coupure de courant, redémarrage…) est détecté par son battement de cœur et remis
en file automatiquement (R10).

Lancement : python -m app.worker
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select, update

from . import emails, firebase, plans
from .config import settings
from .db import SessionLocal, init_db
from .engine import EngineError, ffmpeg, pipeline, youtube
from .models import Project, Upload, User, WorkerHeartbeat, utcnow
import contextlib

log = logging.getLogger("autocut.worker")

PURGE_EVERY = 3600
HEARTBEAT_EVERY = 15


def project_dir(project_id: str):
    return settings.projects_dir / project_id


# --- File d'attente --------------------------------------------------------


def claim_next(worker_id: str) -> str | None:
    with SessionLocal() as db:
        for _ in range(5):
            candidate = db.execute(
                select(Project.id)
                .where(Project.status == "queued")
                .order_by(Project.priority.desc(), Project.created_at)
                .limit(1)
            ).scalar()
            if candidate is None:
                return None
            now = utcnow()
            claimed = db.execute(
                update(Project)
                .where(Project.id == candidate, Project.status == "queued")
                .values(
                    status="processing",
                    worker_id=worker_id,
                    heartbeat_at=now,
                    started_at=now,
                    attempts=Project.attempts + 1,
                    stage="analyse",
                    progress=0.0,
                    error=None,
                )
            )
            db.commit()
            if claimed.rowcount == 1:
                return candidate
    return None


def requeue_stale() -> int:
    """Remet en file les jobs dont le worker ne donne plus signe de vie."""
    limit = utcnow() - timedelta(seconds=settings.job_stale_seconds)
    count = 0
    with SessionLocal() as db:
        stale = db.scalars(
            select(Project).where(Project.status == "processing", Project.heartbeat_at < limit)
        ).all()
        for project in stale:
            if project.attempts >= settings.job_max_attempts:
                _mark_failed(db, project, "Le traitement a été interrompu à plusieurs reprises.")
            else:
                project.status = "queued"
                project.stage = "attente"
                project.progress = 0.0
                project.worker_id = None
            count += 1
        db.commit()
    if count:
        log.warning("%d job(s) interrompu(s) remis en file", count)
    return count


def _mark_failed(db, project: Project, message: str) -> None:
    project.status = "failed"
    project.error = message
    project.finished_at = utcnow()
    project.worker_id = None
    user = db.get(User, project.user_id)
    if project.credit_charged and user is not None:
        plans.refund_credit(user)  # F-TRT-06 : crédit remboursé automatiquement
        project.credit_charged = False
    if user is not None and user.preferences().get("notify_email"):
        emails.send_project_failed(user.email, project.title, project.id)


# --- Exécution ---------------------------------------------------------------


class _Reporter:
    """Écrit l'avancement en base, au plus une fois par seconde (sauf changement d'étape)."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._last = 0.0
        self._stage = ""

    def __call__(self, stage: str, progress: float) -> None:
        now = time.monotonic()
        if stage == self._stage and now - self._last < 1.0 and progress < 1.0:
            return
        self._last, self._stage = now, stage
        with SessionLocal() as db:
            db.execute(
                update(Project)
                .where(Project.id == self.project_id, Project.status == "processing")
                .values(stage=stage, progress=round(progress, 4), heartbeat_at=utcnow())
            )
            db.commit()


def _heartbeat_loop(project_id: str, stop: threading.Event, worker_id: str | None) -> None:
    while not stop.wait(HEARTBEAT_EVERY):
        if worker_id:
            # Le worker reste « en ligne » pendant un long montage (indicateur Moteur IA).
            _beat(worker_id)
        with SessionLocal() as db:
            db.execute(
                update(Project)
                .where(Project.id == project_id, Project.status == "processing")
                .values(heartbeat_at=utcnow())
            )
            db.commit()


def process(project_id: str, worker_id: str | None = None) -> None:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            return
        user = db.get(User, project.user_id)
        plan = plans.plan_for(user)
        options = dict(project.options or {})
        kind, source_kind, source_url = project.job_kind, project.source_kind, project.source_url
        source_filename = project.source_filename
        title = project.title

    workdir = project_dir(project_id)
    workdir.mkdir(parents=True, exist_ok=True)
    report = _Reporter(project_id)
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat_loop, args=(project_id, stop, worker_id), daemon=True)
    beat.start()
    try:
        if source_kind == "storage" and not any(workdir.glob("source.*")):
            report("analyse", 0.0)
            suffix = Path(source_filename).suffix.lower() or ".mp4"
            try:
                source = firebase.download(
                    source_url, workdir / f"source{suffix}", settings.max_upload_bytes,
                    lambda f: report("analyse", 0.1 * f),
                )
            except firebase.FirebaseError as exc:
                raise EngineError(str(exc)) from exc
            info = ffmpeg.probe(source)
            if info["duration"] > plan.max_duration_s + 1:
                raise EngineError(
                    f"Cette vidéo dure plus de {plan.max_duration_s // 60} min, "
                    "la limite de votre offre."
                )
        if source_kind == "youtube" and not any(workdir.glob("source.*")):
            report("analyse", 0.0)
            source = youtube.download(source_url, workdir, lambda f: report("analyse", 0.1 * f))
            info = ffmpeg.probe(source)
            if info["duration"] > plan.max_duration_s + 1:
                raise EngineError(
                    f"Cette vidéo dure plus de {plan.max_duration_s // 60} min, "
                    "la limite de votre offre."
                )
        result = pipeline.run(
            workdir,
            options,
            watermark=settings.brand if plan.watermark else None,
            report=report,
            rerender=kind == "rerender",
        )
    except EngineError as exc:
        log.warning("Montage %s en échec : %s", project_id, exc)
        _finish_failed(project_id, str(exc).split("\n")[0])
        return
    except Exception:
        log.exception("Erreur inattendue pendant le montage %s", project_id)
        _finish_failed(project_id, "Une erreur inattendue est survenue pendant le traitement.")
        return
    finally:
        stop.set()

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:  # supprimé pendant le traitement
            shutil.rmtree(workdir, ignore_errors=True)
            return
        project.status = "done"
        project.stage = "termine"
        project.progress = 1.0
        project.error = None
        project.worker_id = None
        project.finished_at = utcnow()
        project.duration_in = result.duration_in
        project.duration_out = result.duration_out
        project.cuts = result.cuts
        project.language = result.language
        project.width, project.height, project.fps = result.width, result.height, result.fps
        user = db.get(User, project.user_id)
        db.commit()
        if user and user.preferences().get("notify_email") and kind == "full":
            emails.send_project_done(user.email, title, project_id)
    log.info("Montage %s terminé (%.1fs → %.1fs)", project_id, result.duration_in, result.duration_out)


def _finish_failed(project_id: str, message: str) -> None:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            return
        _mark_failed(db, project, message)
        db.commit()


# --- Purge (rétention 30 jours, §8.3) ----------------------------------------


def purge_expired() -> int:
    now = utcnow()
    removed = 0
    with SessionLocal() as db:
        expired = db.scalars(
            select(Project).where(Project.expires_at < now, Project.status != "processing")
        ).all()
        for project in expired:
            shutil.rmtree(project_dir(project.id), ignore_errors=True)
            db.delete(project)
            removed += 1
        stale_uploads = db.scalars(
            select(Upload).where(Upload.created_at < now - timedelta(hours=24))
        ).all()
        for upload in stale_uploads:
            if not upload.consumed:
                with contextlib.suppress(OSError):
                    os.remove(upload.path)
            db.delete(upload)
        db.execute(
            delete(WorkerHeartbeat).where(WorkerHeartbeat.last_seen < now - timedelta(days=1))
        )
        db.commit()
    if removed:
        log.info("Purge : %d projet(s) expiré(s) supprimé(s)", removed)
    return removed


# --- Boucle principale ----------------------------------------------------------


def _beat(worker_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(WorkerHeartbeat, worker_id)
        if row is None:
            db.add(WorkerHeartbeat(worker_id=worker_id, last_seen=utcnow()))
        else:
            row.last_seen = utcnow()
        db.commit()


def run_forever(stop: threading.Event | None = None, worker_id: str | None = None) -> None:
    stop = stop or threading.Event()
    worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{threading.get_ident() % 10000}"
    log.info("Worker %s démarré (FFmpeg %s)", worker_id, ffmpeg.ffmpeg_version())
    last_purge = 0.0
    last_stale_check = 0.0
    while not stop.is_set():
        try:
            _beat(worker_id)
            now = time.monotonic()
            if now - last_stale_check > 30:
                requeue_stale()
                last_stale_check = now
            if now - last_purge > PURGE_EVERY:
                purge_expired()
                last_purge = now
            project_id = claim_next(worker_id)
            if project_id:
                log.info("Montage %s pris en charge", project_id)
                process(project_id, worker_id)
                continue
        except Exception:
            log.exception("Erreur dans la boucle du worker")
        stop.wait(settings.worker_poll_seconds)
    log.info("Worker %s arrêté", worker_id)


def start_background() -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()
    thread = threading.Thread(target=run_forever, args=(stop,), name="autocut-worker", daemon=True)
    thread.start()
    return thread, stop


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    stop = threading.Event()

    def _stop(*_):
        log.info("Arrêt demandé, fin du job en cours…")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    run_forever(stop)


if __name__ == "__main__":
    main()
