"""Intégration Firebase côté serveur : vérification des jetons d'identité et accès au Storage.

- Authentification : l'interface se connecte avec Firebase Auth et envoie son jeton
  d'identité (ID token) à chaque requête. Le serveur le vérifie avec les clés publiques
  de Google : aucune clé secrète de compte de service n'est nécessaire.
- Stockage : les vidéos sont envoyées par l'interface dans Firebase Storage, sous
  « users/{uid}/ ». Le worker les télécharge grâce à l'URL de téléchargement fournie.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

from .config import settings

log = logging.getLogger("autocut.firebase")

STORAGE_HOST = "firebasestorage.googleapis.com"


class FirebaseError(Exception):
    pass


def enabled() -> bool:
    return bool(settings.firebase_project_id)


def _emulator() -> bool:
    return bool(settings.firebase_auth_emulator_host) and not settings.is_production


def looks_like_firebase_token(token: str) -> bool:
    """Les jetons Firebase sont émis par securetoken.google.com/<projet>."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return False
    return str(claims.get("iss", "")).startswith("https://securetoken.google.com/")


def verify_id_token(token: str) -> dict:
    """Renvoie les informations du jeton (uid, e-mail, nom…) ou lève FirebaseError."""
    if not enabled():
        raise FirebaseError("Firebase n'est pas configuré sur ce serveur.")
    if _emulator():
        # Émulateur local : jetons non signés (alg « none »). Jamais accepté en production.
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
        except (IndexError, ValueError) as exc:
            raise FirebaseError("Jeton invalide.") from exc
        if claims.get("aud") != settings.firebase_project_id or claims.get("exp", 0) < time.time():
            raise FirebaseError("Jeton expiré ou destiné à un autre projet.")
    else:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        try:
            claims = id_token.verify_firebase_token(
                token, google_requests.Request(), audience=settings.firebase_project_id
            )
        except Exception as exc:  # signature, expiration, audience…
            raise FirebaseError("Jeton Firebase invalide.") from exc
        if not claims or claims.get("iss") != f"https://securetoken.google.com/{settings.firebase_project_id}":
            raise FirebaseError("Jeton Firebase invalide.")
    uid = claims.get("user_id") or claims.get("sub")
    if not uid:
        raise FirebaseError("Jeton sans identifiant utilisateur.")
    return {**claims, "uid": uid}


# --- Storage -------------------------------------------------------------------------


def _bucket() -> str:
    return settings.firebase_storage_bucket


def validate_storage_source(uid: str, path: str, url: str) -> None:
    """Le fichier doit appartenir à l'utilisateur et l'URL pointer vers notre bucket."""
    if not path.startswith(f"users/{uid}/") or ".." in path:
        raise FirebaseError("Ce fichier n'appartient pas à votre espace.")
    parsed = urlparse(url)
    expected_path = f"/v0/b/{_bucket()}/o/{quote(path, safe='')}"
    allowed_hosts = {STORAGE_HOST}
    if _emulator() and settings.firebase_storage_emulator_host:
        allowed_hosts.add(settings.firebase_storage_emulator_host)
    if parsed.netloc not in allowed_hosts or parsed.path != expected_path:
        raise FirebaseError("Adresse du fichier invalide.")
    if parsed.scheme != "https" and parsed.netloc == STORAGE_HOST:
        raise FirebaseError("Adresse du fichier invalide.")


def download(url: str, target: Path, max_bytes: int, on_progress=None) -> Path:
    """Télécharge la vidéo source depuis Firebase Storage (taille plafonnée)."""
    try:
        with requests.get(url, stream=True, timeout=60) as response:
            if response.status_code != 200:
                raise FirebaseError(f"Fichier introuvable dans le stockage (HTTP {response.status_code}).")
            total = int(response.headers.get("content-length") or 0)
            if total > max_bytes:
                raise FirebaseError("La vidéo dépasse la taille maximale autorisée.")
            received = 0
            with open(target, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    received += len(chunk)
                    if received > max_bytes:
                        raise FirebaseError("La vidéo dépasse la taille maximale autorisée.")
                    handle.write(chunk)
                    if on_progress and total:
                        on_progress(received / total)
    except requests.RequestException as exc:
        raise FirebaseError("Téléchargement de la vidéo impossible depuis le stockage.") from exc
    return target
