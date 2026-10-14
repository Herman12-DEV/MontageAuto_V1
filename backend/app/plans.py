"""Offres commerciales et gestion du quota de crédits (F-PAI-01/02/05)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import User, utcnow


@dataclass(frozen=True)
class Plan:
    key: str
    label: str
    price_eur: float
    monthly_videos: int | None  # None = illimité
    max_duration_s: int
    watermark: bool
    priority: int
    max_active_jobs: int
    features: tuple[str, ...]


PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free",
        label="Plan gratuit",
        price_eur=0,
        monthly_videos=2,
        max_duration_s=5 * 60,
        watermark=True,
        priority=0,
        max_active_jobs=1,
        features=("2 vidéos par mois", "Vidéos jusqu’à 5 min", "Filigrane", "File standard"),
    ),
    "pro": Plan(
        key="pro",
        label="Plan Pro",
        price_eur=7,
        monthly_videos=None,
        max_duration_s=30 * 60,
        watermark=False,
        priority=10,
        max_active_jobs=5,
        features=("Vidéos illimitées", "Jusqu’à 30 min", "Sans filigrane", "File prioritaire"),
    ),
    "agence": Plan(
        key="agence",
        label="Plan Agence",
        price_eur=29,
        monthly_videos=None,
        max_duration_s=30 * 60,
        watermark=False,
        priority=20,
        max_active_jobs=5,
        features=(
            "Vidéos illimitées",
            "Traitement par lot (5 en file)",
            "Sans filigrane",
            "Support prioritaire",
        ),
    ),
}


def plan_for(user: User) -> Plan:
    return PLANS.get(user.plan, PLANS["free"])


def current_period() -> str:
    return utcnow().strftime("%Y-%m")


def _roll_period(user: User) -> None:
    period = current_period()
    if user.credits_period != period:
        user.credits_period = period
        user.credits_used = 0


def quota(user: User) -> dict:
    _roll_period(user)
    plan = plan_for(user)
    limit = plan.monthly_videos
    remaining = None if limit is None else max(0, limit - user.credits_used)
    return {
        "plan": plan.key,
        "plan_label": plan.label,
        "used": user.credits_used,
        "limit": limit,
        "remaining": remaining,
        "unlimited": limit is None,
        "max_duration_s": plan.max_duration_s,
        "watermark": plan.watermark,
        "period": user.credits_period,
    }


def has_credit(user: User) -> bool:
    q = quota(user)
    return q["unlimited"] or q["remaining"] > 0


def charge_credit(user: User) -> None:
    _roll_period(user)
    user.credits_used += 1


def refund_credit(user: User) -> None:
    _roll_period(user)
    user.credits_used = max(0, user.credits_used - 1)


def public_plans() -> list[dict]:
    return [asdict(p) for p in PLANS.values()]
