"""Envoi d'e-mails. Sans SMTP configuré, les messages sont écrits dans storage/outbox (dev)."""

from __future__ import annotations

import logging
import re
import smtplib
import threading
from email.message import EmailMessage
from html import escape

from .config import settings
from .models import new_id, utcnow

log = logging.getLogger("autocut.mail")


def _html(title: str, body: str, action_label: str | None, action_url: str | None) -> str:
    button = (
        f'<p><a href="{escape(action_url)}" style="display:inline-block;padding:12px 20px;'
        f'border-radius:999px;background:#27c66e;color:#071109;font-weight:700;'
        f'text-decoration:none">{escape(action_label)}</a></p>'
        if action_url and action_label
        else ""
    )
    paragraphs = "".join(f"<p>{escape(p)}</p>" for p in body.split("\n\n"))
    return (
        '<div style="font-family:Arial,sans-serif;background:#f3f3ec;padding:28px">'
        '<div style="max-width:520px;margin:auto;background:#090a09;color:#fafaf6;'
        'border-radius:17px;padding:28px">'
        f'<p style="font-weight:800;letter-spacing:-0.05em;text-transform:uppercase">{escape(settings.brand)}</p>'
        f'<h1 style="text-transform:uppercase;letter-spacing:-0.04em">{escape(title)}</h1>'
        f'<div style="color:#b9bab4;line-height:1.6">{paragraphs}</div>{button}</div></div>'
    )


def _deliver(message: EmailMessage) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except Exception:  # un e-mail raté ne doit jamais faire échouer la requête
        log.exception("Échec d'envoi de l'e-mail à %s", message["To"])


def send(
    to: str | None,
    subject: str,
    title: str,
    body: str,
    action_label: str | None = None,
    action_url: str | None = None,
) -> None:
    if not to:
        return  # compte sans adresse e-mail (inscription par nom d'utilisateur)
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = f"{settings.brand} — {subject}"
    text = body + (f"\n\n{action_label} : {action_url}" if action_url else "")
    message.set_content(text)
    message.add_alternative(_html(title, body, action_label, action_url), subtype="html")

    if settings.smtp_host:
        threading.Thread(target=_deliver, args=(message,), daemon=True).start()
        return
    settings.outbox_dir.mkdir(parents=True, exist_ok=True)
    safe_to = re.sub(r"[^\w.@-]", "_", to)
    path = settings.outbox_dir / f"{utcnow():%Y%m%d-%H%M%S}-{safe_to}-{new_id()[:6]}.eml"
    path.write_bytes(bytes(message))
    log.warning("[e-mail dev] À %s — %s%s", to, subject, f"\n    → {action_url}" if action_url else "")


def link(path: str) -> str:
    return f"{settings.public_url}/#{path}"


def send_reset(to: str | None, token: str) -> None:
    send(
        to,
        "Réinitialisation du mot de passe",
        "Nouveau mot de passe",
        "Vous avez demandé à réinitialiser votre mot de passe. Ce lien est valable 1 heure.\n\n"
        "Si vous n’êtes pas à l’origine de cette demande, ignorez simplement cet e-mail.",
        "Choisir un nouveau mot de passe",
        link(f"/reinitialiser?token={token}"),
    )


def send_project_done(to: str | None, title: str, project_id: str) -> None:
    send(
        to,
        "Votre montage est prêt",
        "Montage terminé",
        f"Votre vidéo « {title} » a été montée automatiquement et est prête à être téléchargée.\n\n"
        f"Elle reste disponible pendant {settings.retention_days} jours.",
        "Voir mon montage",
        link(f"/app/termine?id={project_id}"),
    )


def send_project_failed(to: str | None, title: str, project_id: str) -> None:
    send(
        to,
        "Le montage n’a pas abouti",
        "Un problème est survenu",
        f"Le traitement de « {title} » a échoué. Votre crédit a été automatiquement remboursé.\n\n"
        "Vous pouvez relancer le montage en un clic.",
        "Réessayer",
        link(f"/app/termine?id={project_id}"),
    )


def send_receipt(to: str | None, plan_label: str, amount: str) -> None:
    send(
        to,
        "Merci pour votre abonnement",
        "Paiement confirmé",
        f"Votre {plan_label} est actif immédiatement. Montant réglé : {amount}.\n\n"
        "Le reçu officiel de votre paiement vous est également envoyé par Stripe.",
        "Créer un montage",
        link("/app/nouveau"),
    )
