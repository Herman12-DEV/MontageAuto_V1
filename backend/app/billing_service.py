"""Abonnements via Stripe Checkout + webhooks (F-PAI-02, F-PAI-03, F-PAI-05)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import emails
from .config import settings
from .models import Payment, User, utcnow
from .plans import PLANS

log = logging.getLogger("autocut.billing")


class BillingError(Exception):
    pass


def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key)


def _stripe():
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _price(plan: str) -> str:
    price = {"pro": settings.stripe_price_pro, "agence": settings.stripe_price_agence}.get(plan, "")
    if not price:
        raise BillingError("Cette offre n’est pas encore disponible au paiement.")
    return price


def activate(user: User, plan: str, renews_at: datetime | None = None) -> None:
    user.plan = plan
    user.plan_renews_at = renews_at or (utcnow() + timedelta(days=30))


def checkout(db: Session, user: User, plan: str) -> dict:
    if plan not in ("pro", "agence"):
        raise BillingError("Offre inconnue.")
    if not stripe_enabled():
        if not settings.dev_fake_payments:
            raise BillingError("Le paiement en ligne n’est pas encore configuré sur ce serveur.")
        # Mode démonstration : activation immédiate, sans débit.
        activate(user, plan)
        db.commit()
        emails.send_receipt(user.email, PLANS[plan].label, "0,00 € (mode démonstration)")
        return {"url": None, "activated": True}

    stripe = _stripe()
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            **({"email": user.email} if user.email else {}),
            name=user.name or user.username or None,
            metadata={"user_id": user.id},
        )
        user.stripe_customer_id = customer.id
        db.commit()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=user.stripe_customer_id,
        line_items=[{"price": _price(plan), "quantity": 1}],
        client_reference_id=user.id,
        metadata={"user_id": user.id, "plan": plan},
        subscription_data={"metadata": {"user_id": user.id, "plan": plan}},
        success_url=f"{settings.public_url}/#/app/profil?paiement=ok",
        cancel_url=f"{settings.public_url}/#/app/profil?paiement=annule",
        locale="fr",
        allow_promotion_codes=True,
    )
    return {"url": session.url, "activated": False}


def portal(user: User) -> str:
    if not stripe_enabled() or not user.stripe_customer_id:
        raise BillingError("Aucun abonnement payant à gérer.")
    session = _stripe().billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=f"{settings.public_url}/#/app/profil"
    )
    return session.url


def cancel_subscription(user: User) -> None:
    """Annule l'abonnement Stripe (suppression de compte)."""
    if stripe_enabled() and user.stripe_subscription_id:
        try:
            _stripe().Subscription.cancel(user.stripe_subscription_id)
        except Exception:
            log.exception("Annulation Stripe impossible pour %s", user.id)


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC).replace(tzinfo=None) if value else None


def handle_webhook(db: Session, payload: bytes, signature: str) -> str:
    stripe = _stripe()
    try:
        stripe.WebhookSignature.verify_header(
            payload.decode("utf-8"), signature, settings.stripe_webhook_secret, tolerance=300
        )
        event = json.loads(payload)
    except Exception as exc:
        raise BillingError("Signature de webhook invalide.") from exc

    if db.scalar(select(Payment).where(Payment.stripe_event_id == event["id"])):
        return "déjà traité"
    obj = event["data"]["object"]
    kind = event["type"]
    user: User | None = None
    plan: str | None = None
    amount = None

    if kind == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        user = db.get(User, meta.get("user_id") or obj.get("client_reference_id"))
        plan = meta.get("plan")
        amount = obj.get("amount_total")
        if user and plan in PLANS:
            user.stripe_customer_id = obj.get("customer") or user.stripe_customer_id
            user.stripe_subscription_id = obj.get("subscription")
            activate(user, plan)
            total = f"{(amount or 0) / 100:.2f} {str(obj.get('currency', 'eur')).upper()}"
            emails.send_receipt(user.email, PLANS[plan].label, total.replace(".", ","))
    elif kind in ("customer.subscription.updated", "customer.subscription.created"):
        meta = obj.get("metadata") or {}
        user = db.get(User, meta.get("user_id")) if meta.get("user_id") else None
        if user is None:
            user = db.scalar(select(User).where(User.stripe_customer_id == obj.get("customer")))
        plan = meta.get("plan")
        if user:
            if obj.get("status") in ("active", "trialing") and plan in PLANS:
                user.stripe_subscription_id = obj.get("id")
                activate(user, plan, _ts(obj.get("current_period_end")))
            elif obj.get("status") in ("canceled", "unpaid", "incomplete_expired"):
                user.plan, user.plan_renews_at, user.stripe_subscription_id = "free", None, None
    elif kind == "customer.subscription.deleted":
        user = db.scalar(select(User).where(User.stripe_customer_id == obj.get("customer")))
        if user:
            user.plan, user.plan_renews_at, user.stripe_subscription_id = "free", None, None
    elif kind == "invoice.paid":
        user = db.scalar(select(User).where(User.stripe_customer_id == obj.get("customer")))
        amount = obj.get("amount_paid")
        if user and user.plan != "free":
            lines = (obj.get("lines") or {}).get("data") or []
            end = _ts(lines[0].get("period", {}).get("end")) if lines else None
            user.plan_renews_at = end or (utcnow() + timedelta(days=30))

    db.add(
        Payment(
            user_id=user.id if user else None,
            stripe_event_id=event["id"],
            kind=kind,
            plan=plan,
            amount_cents=amount,
            currency=obj.get("currency"),
        )
    )
    db.commit()
    return kind
