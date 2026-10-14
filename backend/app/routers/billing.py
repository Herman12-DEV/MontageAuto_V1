"""Offres et paiement."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import billing_service
from ..db import get_db
from ..deps import api_error, current_user
from ..models import User
from ..plans import public_plans
from ..serializers import user_out

router = APIRouter(prefix="/api/billing", tags=["paiement"])


class CheckoutIn(BaseModel):
    plan: Literal["pro", "agence"]


@router.get("/plans")
def plans():
    return {"plans": public_plans(), "payments_enabled": billing_service.stripe_enabled()}


@router.post("/checkout")
def checkout(body: CheckoutIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.plan == body.plan:
        raise api_error(409, "already_subscribed", "Cette offre est déjà active sur votre compte.")
    try:
        result = billing_service.checkout(db, user, body.plan)
    except billing_service.BillingError as exc:
        raise api_error(503, "billing_unavailable", str(exc)) from exc
    return {**result, "user": user_out(user)}


@router.post("/portal")
def portal(user: User = Depends(current_user)):
    try:
        return {"url": billing_service.portal(user)}
    except billing_service.BillingError as exc:
        raise api_error(400, "no_subscription", str(exc)) from exc


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db)):
    if not billing_service.stripe_enabled():
        raise api_error(404, "disabled", "Paiement non configuré.")
    payload = await request.body()
    try:
        handled = billing_service.handle_webhook(db, payload, request.headers.get("stripe-signature", ""))
    except billing_service.BillingError as exc:
        raise api_error(400, "invalid_signature", str(exc)) from exc
    return {"received": handled}
