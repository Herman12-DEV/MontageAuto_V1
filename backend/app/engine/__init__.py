"""Moteur de montage : FFmpeg (analyse, coupe, habillage) + Whisper (transcription)."""


class EngineError(Exception):
    """Erreur de traitement dont le message est montrable tel quel à l'utilisateur."""
