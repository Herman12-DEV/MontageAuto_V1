"""Transcription mot à mot avec faster-whisper (F-ST-01, F-ST-02)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import types
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

from ..config import settings
from . import EngineError
import contextlib

log = logging.getLogger(__name__)

_models: dict[str, object] = {}
_lock = threading.Lock()

SUPPORTED_LANGUAGES = {"fr", "en"}


def _import_faster_whisper():
    # faster-whisper importe PyAV uniquement pour décoder l'audio, ce que fait déjà FFmpeg.
    # Si PyAV ne se charge pas (DLL bloquée par la politique Windows, build absent…), on
    # le remplace par un module vide : l'audio est fourni en tableau numpy.
    try:
        import av  # noqa: F401
    except ImportError:
        for name in [m for m in sys.modules if m == "av" or m.startswith("av.")]:
            del sys.modules[name]
        sys.modules["av"] = types.ModuleType("av")
    from faster_whisper import WhisperModel

    return WhisperModel


def load_wav(path: Path) -> np.ndarray:
    """WAV PCM 16 bits mono 16 kHz (produit par FFmpeg) → float32 normalisé."""
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1 or wav.getframerate() != 16000:
            raise EngineError("Format audio intermédiaire inattendu.")
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def _model(name: str):
    with _lock:
        if name not in _models:
            try:
                WhisperModel = _import_faster_whisper()
            except ImportError as exc:  # pragma: no cover - dépendance installée par requirements
                raise EngineError("Le moteur de transcription n’est pas installé.") from exc
            log.info("Chargement du modèle Whisper « %s »…", name)
            _models[name] = WhisperModel(
                name,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
                cpu_threads=settings.whisper_threads or (os.cpu_count() or 4),
                download_root=settings.whisper_models_dir or str(settings.storage_dir / "models"),
            )
        return _models[name]


def transcribe(
    audio: Path,
    duration: float,
    language: str = "auto",
    on_progress: Callable[[float], None] | None = None,
) -> dict:
    """Renvoie {"language": "fr", "words": [{"w": "Bonjour", "s": 0.12, "e": 0.48}, ...]}."""
    model = _model(settings.whisper_model)
    samples = load_wav(audio)
    if samples.size < 1600:  # moins de 0,1 s de parole
        return {"language": None if language == "auto" else language, "words": []}
    segments, info = model.transcribe(
        samples,
        language=None if language in ("", "auto") else language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        beam_size=max(1, settings.whisper_beam_size),
        condition_on_previous_text=False,  # limite les répétitions / hallucinations
    )
    words: list[dict] = []
    for segment in segments:
        first_in_segment = True
        for word in segment.words or []:
            text = word.word.strip()
            if not text:
                continue
            # Un fragment sans espace initial prolonge le mot précédent (« Aujourd » + « 'hui »).
            if words and not first_in_segment and not word.word.startswith(" "):
                words[-1]["w"] += text
                words[-1]["e"] = round(word.end, 3)
                continue
            words.append({"w": text, "s": round(word.start, 3), "e": round(word.end, 3)})
            first_in_segment = False
        if on_progress and duration:
            on_progress(min(1.0, segment.end / duration))
    return {"language": info.language, "words": words}


def transcribe_isolated(
    audio: Path,
    duration: float,
    language: str = "auto",
    on_progress: Callable[[float], None] | None = None,
) -> dict:
    """Même chose dans un processus séparé : la mémoire du modèle (≈1 Go) est rendue au
    système avant l'encodage FFmpeg, ce qui évite les échecs sur les petits serveurs."""
    out = audio.with_suffix(".json")
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.engine.transcribe", str(audio), str(out), language, str(duration)],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    stderr: list[str] = []
    reader = threading.Thread(target=lambda: stderr.extend(proc.stderr), daemon=True)
    reader.start()
    assert proc.stdout is not None
    for line in proc.stdout:
        if line.startswith("PROGRESS ") and on_progress:
            with contextlib.suppress(ValueError):
                on_progress(float(line.split()[1]))
    proc.wait()
    reader.join(timeout=5)
    try:
        if proc.returncode != 0:
            for line in reversed(stderr):
                if line.startswith("ENGINE_ERROR "):
                    raise EngineError(line[len("ENGINE_ERROR ") :].strip())
            details = "".join(stderr[-20:])
            log.error("Transcription en échec :\n%s", details)
            if "allocate memory" in details or "MemoryError" in details:
                raise EngineError("Le serveur est momentanément saturé. Réessayez dans quelques minutes.")
            raise EngineError("La transcription a échoué.")
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        out.unlink(missing_ok=True)


def _main(argv: list[str]) -> int:
    audio, out, language, duration = Path(argv[0]), Path(argv[1]), argv[2], float(argv[3])
    try:
        result = transcribe(
            audio, duration, language, lambda f: print(f"PROGRESS {f:.4f}", flush=True)
        )
    except EngineError as exc:
        print(f"ENGINE_ERROR {exc}", file=sys.stderr, flush=True)
        return 2
    out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(_main(sys.argv[1:]))
