"""Tables : utilisateurs, téléversements, projets (qui servent aussi de file d'attente)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    """Horodatage UTC « naïf » : stocké tel quel en SQLite comme en PostgreSQL."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex


DEFAULT_PREFS = {
    "language": "auto",
    "subtitle_style": "karaoke",
    "format": "9:16",
    "notify_email": True,
    "auto_analyse": False,
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # Identifiant de connexion choisi à l'inscription (stocké en minuscules).
    username: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)
    # Facultatif : renseigné par Google, ou ajouté depuis le profil (récupération du mot de passe).
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    # Vide pour un compte créé uniquement via Google.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    # Identifiant du compte Firebase Auth (connexion via l'interface).
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    plan_renews_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prefs: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_PREFS))
    # Quota mensuel : nombre de crédits consommés sur la période « AAAA-MM ».
    credits_period: Mapped[str] = mapped_column(String(7), default="")
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    # Incrémenté à chaque changement de mot de passe : invalide les anciens jetons.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    projects: Mapped[list[Project]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def preferences(self) -> dict:
        return {**DEFAULT_PREFS, **(self.prefs or {})}


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer)
    received: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str] = mapped_column(String(500))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Résultat de ffprobe une fois le fichier complet et validé.
    probe: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Project(Base):
    """Un montage. La table sert aussi de file d'attente pour les workers."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source_kind: Mapped[str] = mapped_column(String(10), default="upload")  # upload | youtube | storage
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Chemin du fichier source dans Firebase Storage (« users/{uid}/sources/… »).
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), default="")
    options: Mapped[dict] = mapped_column(JSON, default=dict)

    # queued | processing | done | failed
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    job_kind: Mapped[str] = mapped_column(String(10), default="full")  # full | rerender
    stage: Mapped[str] = mapped_column(String(16), default="attente")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    credit_charged: Mapped[bool] = mapped_column(Boolean, default=False)

    # Résultats
    duration_in: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_out: Mapped[float | None] = mapped_column(Float, nullable=True)
    cuts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    user: Mapped[User] = relationship(back_populates="projects")


class WorkerHeartbeat(Base):
    """Présence des workers : alimente l'indicateur « Moteur IA en ligne »."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Payment(Base):
    """Traçabilité des paiements reçus via Stripe (webhooks)."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stripe_event_id: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(60))
    plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
