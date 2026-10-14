"""Noms d'utilisateur : format, normalisation et génération d'un nom libre."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")
USERNAME_RULES = "3 à 30 caractères : lettres, chiffres, point, tiret ou tiret bas."


def normalize_username(value: str) -> str:
    return value.strip().lower()


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.match(value))


def suggest_username(seed: str, taken: Callable[[str], bool]) -> str:
    """Nom libre dérivé d'un e-mail ou d'un nom (« Awa Koné » → « awa.kone », « awa.kone2 »…)."""
    ascii_seed = unicodedata.normalize("NFKD", seed.split("@")[0]).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9._-]+", ".", ascii_seed.lower()).strip("._-")[:26]
    if len(base) < 3:
        base = (base + "user")[:26]
    candidate, n = base, 1
    while taken(candidate):
        n += 1
        candidate = f"{base}{n}"
    return candidate
