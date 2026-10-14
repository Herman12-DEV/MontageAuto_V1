"""Application FastAPI : API + service du frontend compilé (dist/) en production.

Lancement en dev : uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import worker
from .config import settings
from .db import init_db
from .routers import auth, billing, library, projects, uploads, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("autocut")


def _check_production_config() -> None:
    if not settings.is_production:
        return
    problems = []
    if not os.getenv("SECRET_KEY"):
        problems.append("SECRET_KEY doit être défini")
    if settings.dev_fake_payments:
        problems.append("DEV_FAKE_PAYMENTS doit valoir false")
    if settings.firebase_auth_emulator_host:
        problems.append("FIREBASE_AUTH_EMULATOR_HOST doit être vide (émulateur réservé au développement)")
    if not settings.public_url.startswith("https://"):
        problems.append("PUBLIC_URL doit être en https://")
    if problems:
        raise RuntimeError("Configuration de production invalide : " + " ; ".join(problems))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _check_production_config()
    init_db()
    background = None
    if settings.embedded_worker:
        # Pratique en dev : un worker tourne dans le même processus que l'API.
        background = worker.start_background()
    yield
    if background:
        background[1].set()


app = FastAPI(
    title=f"{settings.brand} API",
    version="1.0.0",
    description="Montage vidéo automatique : silences, sous-titres karaoké, musique, recadrage.",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


_FIELD_LABELS = {"username": "Le nom d’utilisateur", "identifier": "L’identifiant", "email": "L’e-mail", "password": "Le mot de passe", "new_password": "Le mot de passe", "name": "Le nom"}


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = str(first.get("loc", ["", ""])[-1])
    label = _FIELD_LABELS.get(field)
    if field in ("password", "new_password") and first.get("type") == "string_too_short":
        message = "Le mot de passe doit contenir au moins 8 caractères."
    elif field == "email":
        message = "Adresse e-mail invalide."
    elif label:
        message = f"{label} est invalide."
    else:
        message = "Requête invalide."
    return JSONResponse(status_code=422, content={"detail": {"code": "validation", "message": message}})


for module in (auth, users, uploads, projects, library, billing):
    app.include_router(module.router)


# --- Frontend compilé (production) ---------------------------------------------
if settings.frontend_dist.exists():
    assets = settings.frontend_dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": {"code": "not_found", "message": "Introuvable."}})
        candidate = (settings.frontend_dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(settings.frontend_dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist / "index.html")
