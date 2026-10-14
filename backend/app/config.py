"""Configuration lue depuis les variables d'environnement (fichier .env accepté)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "oui", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _secret_key() -> str:
    value = os.getenv("SECRET_KEY")
    if value:
        return value
    # En dev, on persiste une clé aléatoire pour que les sessions survivent aux redémarrages.
    key_file = BACKEND_DIR / "storage" / ".secret_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if not key_file.exists():
        key_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return key_file.read_text(encoding="utf-8").strip()


@dataclass
class Settings:
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    brand: str = field(default_factory=lambda: os.getenv("BRAND_NAME", "AutoCut"))
    secret_key: str = field(default_factory=_secret_key)
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'storage' / 'autocut.db').as_posix()}"
        )
    )
    storage_dir: Path = field(
        default_factory=lambda: Path(os.getenv("STORAGE_DIR", str(BACKEND_DIR / "storage")))
    )
    music_dir: Path = field(
        default_factory=lambda: Path(os.getenv("MUSIC_DIR", str(BACKEND_DIR / "music")))
    )
    frontend_dist: Path = field(
        default_factory=lambda: Path(
            os.getenv("FRONTEND_DIST", str(BACKEND_DIR.parent / "dist"))
        )
    )
    # URL publique du site (utilisée dans les liens des e-mails et les retours Stripe).
    public_url: str = field(
        default_factory=lambda: os.getenv("PUBLIC_URL", "http://localhost:5173").rstrip("/")
    )
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
        ]
    )

    # Moteur
    ffmpeg_bin: str = field(default_factory=lambda: os.getenv("FFMPEG_BIN", "ffmpeg"))
    ffprobe_bin: str = field(default_factory=lambda: os.getenv("FFPROBE_BIN", "ffprobe"))
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "small"))
    whisper_compute_type: str = field(
        default_factory=lambda: os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    )
    whisper_device: str = field(default_factory=lambda: os.getenv("WHISPER_DEVICE", "cpu"))
    # Dossier du cache des modèles Whisper (partageable entre plusieurs workers).
    whisper_models_dir: str = field(default_factory=lambda: os.getenv("WHISPER_MODELS_DIR", "").strip())
    # 0 = tous les cœurs disponibles (faster-whisper n'en utilise que 4 par défaut).
    whisper_threads: int = field(default_factory=lambda: _int("WHISPER_THREADS", 0))
    # 5 = précision maximale ; 1 = décodage glouton, environ 2× plus rapide.
    whisper_beam_size: int = field(default_factory=lambda: _int("WHISPER_BEAM_SIZE", 5))
    x264_preset: str = field(default_factory=lambda: os.getenv("X264_PRESET", "veryfast"))
    x264_crf: int = field(default_factory=lambda: _int("X264_CRF", 20))

    # File d'attente
    embedded_worker: bool = field(default_factory=lambda: _bool("EMBEDDED_WORKER", True))
    worker_poll_seconds: float = field(default_factory=lambda: _float("WORKER_POLL_SECONDS", 2.0))
    job_stale_seconds: int = field(default_factory=lambda: _int("JOB_STALE_SECONDS", 180))
    job_max_attempts: int = field(default_factory=lambda: _int("JOB_MAX_ATTEMPTS", 2))

    # Limites
    max_upload_bytes: int = field(
        default_factory=lambda: _int("MAX_UPLOAD_MB", 500) * 1024 * 1024
    )
    upload_chunk_bytes: int = field(
        default_factory=lambda: _int("UPLOAD_CHUNK_MB", 8) * 1024 * 1024
    )
    retention_days: int = field(default_factory=lambda: _int("RETENTION_DAYS", 30))

    # E-mail (si SMTP_HOST est vide, les e-mails sont écrits dans storage/outbox et la console)
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: _int("SMTP_PORT", 587))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_tls: bool = field(default_factory=lambda: _bool("SMTP_TLS", True))
    mail_from: str = field(
        default_factory=lambda: os.getenv("MAIL_FROM", "AutoCut <no-reply@localhost>")
    )

    # Paiement
    stripe_secret_key: str = field(default_factory=lambda: os.getenv("STRIPE_SECRET_KEY", ""))
    stripe_webhook_secret: str = field(
        default_factory=lambda: os.getenv("STRIPE_WEBHOOK_SECRET", "")
    )
    stripe_price_pro: str = field(default_factory=lambda: os.getenv("STRIPE_PRICE_PRO", ""))
    stripe_price_agence: str = field(
        default_factory=lambda: os.getenv("STRIPE_PRICE_AGENCE", "")
    )
    # Sans clé Stripe, autorise l'activation simulée des offres (dev uniquement).
    dev_fake_payments: bool = field(default_factory=lambda: _bool("DEV_FAKE_PAYMENTS", False))

    # Firebase (authentification + stockage des vidéos importées).
    firebase_project_id: str = field(default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID", "").strip())
    firebase_storage_bucket: str = field(
        default_factory=lambda: os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
    )
    # Émulateurs locaux (développement uniquement), ex. 127.0.0.1:9099 et 127.0.0.1:9199.
    firebase_auth_emulator_host: str = field(
        default_factory=lambda: os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "").strip()
    )
    firebase_storage_emulator_host: str = field(
        default_factory=lambda: os.getenv("FIREBASE_STORAGE_EMULATOR_HOST", "").strip()
    )

    # Connexion Google : identifiant client OAuth (console.cloud.google.com → Identifiants).
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", "").strip())

    rate_limit_enabled: bool = field(default_factory=lambda: _bool("RATE_LIMIT_ENABLED", True))

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def projects_dir(self) -> Path:
        return self.storage_dir / "projects"

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def outbox_dir(self) -> Path:
        return self.storage_dir / "outbox"

    def ensure_dirs(self) -> None:
        for path in (self.storage_dir, self.projects_dir, self.uploads_dir, self.outbox_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
