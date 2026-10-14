"""Webhook Stripe signé (R8) et éditeur de sous-titres (F-ST-06)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta

from app.config import settings
from app.db import SessionLocal
from app.engine import pipeline
from app.models import Payment, Project, User, utcnow
from tests.conftest import register_and_login, sent_subjects


def _signed(payload: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


def test_stripe_webhook_activates_plan_once(client, monkeypatch):
    headers = register_and_login(client, email="awa@example.com")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    with SessionLocal() as db:
        user_id = db.query(User).one().id
    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": user_id,
                "metadata": {"user_id": user_id, "plan": "pro"},
                "customer": "cus_1",
                "subscription": "sub_1",
                "amount_total": 700,
                "currency": "eur",
            }
        },
    }
    body, sig = _signed(event, "whsec_test")
    bad = client.post("/api/billing/webhook", content=body, headers={"stripe-signature": "t=1,v1=00"})
    assert bad.status_code == 400
    for _ in range(2):  # Stripe peut renvoyer un événement : traité une seule fois
        res = client.post("/api/billing/webhook", content=body, headers={"stripe-signature": sig})
        assert res.status_code == 200
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.plan == "pro" and user.stripe_subscription_id == "sub_1"
        assert db.query(Payment).count() == 1
    assert client.get("/api/me", headers=headers).json()["quota"]["unlimited"] is True
    assert any("Merci pour votre abonnement" in s for s in sent_subjects())

    cancel = {"id": "evt_2", "type": "customer.subscription.deleted", "data": {"object": {"customer": "cus_1"}}}
    body, sig = _signed(cancel, "whsec_test")
    assert client.post("/api/billing/webhook", content=body, headers={"stripe-signature": sig}).status_code == 200
    with SessionLocal() as db:
        assert db.get(User, user_id).plan == "free"


def test_transcript_edit_queues_free_rerender(client):
    headers = register_and_login(client)
    with SessionLocal() as db:
        user = db.query(User).one()
        project = Project(
            user_id=user.id,
            title="Démo",
            status="done",
            options={"subtitles": True},
            expires_at=utcnow() + timedelta(days=30),
        )
        db.add(project)
        db.commit()
        pid = project.id
    workdir = settings.projects_dir / pid
    workdir.mkdir(parents=True)
    pipeline.save_transcript(
        workdir,
        {
            "language": "fr",
            "phrases": [
                {"words": [{"w": "Bonjour", "s": 0.0, "e": 0.5}, {"w": "a", "s": 0.5, "e": 0.6}, {"w": "tous", "s": 0.6, "e": 1.0}]},
                {"words": [{"w": "Fin", "s": 2.0, "e": 2.4}]},
            ],
        },
    )
    res = client.get(f"/api/projects/{pid}/transcript", headers=headers)
    assert res.json()["phrases"][0]["text"] == "Bonjour a tous"

    res = client.put(
        f"/api/projects/{pid}/transcript",
        json={"phrases": [{"index": 0, "text": "Bonjour à tous"}, {"index": 1, "text": ""}]},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "queued" and res.json()["job_kind"] == "rerender"
    saved = pipeline.load_transcript(workdir)
    assert len(saved["phrases"]) == 1  # phrase vidée = supprimée
    assert [w["w"] for w in saved["phrases"][0]["words"]] == ["Bonjour", "à", "tous"]
    assert client.get("/api/me", headers=headers).json()["quota"]["used"] == 0
