"""Génère la bibliothèque musicale intégrée : 20 boucles originales synthétisées par FFmpeg.

Ces pistes sont créées de toutes pièces par le projet (aucun échantillon externe) et
publiées sous licence CC0 : elles peuvent être utilisées sans restriction. Le registre
`music/licenses.json` trace l'origine et la licence de chaque fichier (§8.3 du cahier
des charges). Pour ajouter un morceau Creative Commons externe, déposez le fichier dans
`music/` et ajoutez une entrée au registre avec son auteur, sa source et sa licence.

Usage : python -m scripts.generate_music [--force]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.engine import ffmpeg

PROGRESSIONS = {
    "Horizon": [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)],
    "Rivage": [(9, 12, 16), (5, 9, 12), (0, 4, 7), (7, 11, 14)],
    "Nocturne": [(0, 3, 7), (8, 12, 15), (3, 7, 10), (10, 14, 17)],
    "Lumière": [(0, 4, 7), (9, 12, 16), (5, 9, 12), (7, 11, 14)],
    "Velours": [(2, 5, 9), (7, 11, 14), (0, 4, 7), (0, 4, 11)],
}

MOODS = [
    # (nom, note fondamentale MIDI, tempo, batterie, arpège, filtre passe-bas)
    ("Calme", 57, 72, False, False, 1800),
    ("Pop", 60, 100, True, True, 3200),
    ("Énergie", 62, 122, True, True, 4200),
    ("Lo-fi", 55, 82, True, False, 1400),
]


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _pick(chord_values: list[float]) -> str:
    """Expression qui renvoie la valeur correspondant à l'accord courant (variable 0)."""
    a, b, c, d = (f"{v:.4f}" for v in chord_values)
    return f"if(eq(ld(0),0),{a},if(eq(ld(0),1),{b},if(eq(ld(0),2),{c},{d})))"


def _expression(root: int, chords, bpm: int, drums: bool, arp: bool, detune: float) -> str:
    beat = 60.0 / bpm
    bar = beat * 4
    parts = [f"st(0,floor(mod(t,{bar * 4:.5f})/{bar:.5f}))"]  # accord courant 0..3
    env = f"min(1,mod(t,{bar:.5f})/0.35)*(1-0.35*mod(t,{bar:.5f})/{bar:.5f})"
    voices = []
    for voice in range(3):
        freqs = [_hz(root + chord[voice]) * detune for chord in chords]
        f = _pick(freqs)
        voices.append(f"(sin(2*PI*{f}*t)+0.25*sin(4*PI*{f}*t))")
    pad = f"0.11*({'+'.join(voices)})*{env}"
    bass_f = _pick([_hz(root - 12 + chord[0]) for chord in chords])
    bass = f"0.2*sin(2*PI*{bass_f}*t)*(0.55+0.45*exp(-mod(t,{beat:.5f})*3))"
    terms = [pad, bass]
    if arp:
        step = beat / 2
        tones = []
        for voice in range(3):
            tones.append(_pick([_hz(root + 12 + chord[voice]) for chord in chords]))
        sel = f"mod(floor(t/{step:.5f}),3)"
        arp_f = f"if(eq({sel},0),{tones[0]},if(eq({sel},1),{tones[1]},{tones[2]}))"
        terms.append(f"0.07*sin(2*PI*{arp_f}*t)*exp(-mod(t,{step:.5f})*7)")
    if drums:
        terms.append(
            f"0.45*sin(2*PI*52*mod(t,{beat:.5f}))*exp(-mod(t,{beat:.5f})*14)"
        )
        terms.append(
            f"0.05*(random(1)*2-1)*exp(-mod(t+{beat / 2:.5f},{beat:.5f})*40)"
        )
    # st() est évalué en premier (opérande gauche) puis neutralisé par *0.
    return f"{parts[0]}*0+" + "+".join(terms)


def generate(force: bool = False) -> list[dict]:
    out_dir = settings.music_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    registry: list[dict] = []
    number = 0
    for prog_name, chords in PROGRESSIONS.items():
        for mood, root, bpm, drums, arp, cutoff in MOODS:
            number += 1
            track_id = f"autocut-{number:02d}"
            filename = f"{track_id}.mp3"
            cycle = 60.0 / bpm * 16  # 4 accords d'une mesure
            duration = cycle * math.ceil(60 / cycle)
            target = out_dir / filename
            if force or not target.exists():
                left = _expression(root, chords, bpm, drums, arp, 1.0)
                right = _expression(root, chords, bpm, drums, arp, 1.003)
                source = f"aevalsrc='{left}|{right}':s=44100:d={duration:.3f}"
                ffmpeg.run(
                    [
                        "-f",
                        "lavfi",
                        "-i",
                        source,
                        "-af",
                        f"lowpass=f={cutoff},aecho=0.8:0.6:90|180:0.22|0.12,"
                        "alimiter=limit=0.8,volume=0.9",
                        "-c:a",
                        "libmp3lame",
                        "-b:a",
                        "128k",
                        str(target),
                    ]
                )
                print(f"  ✓ {filename}")
            registry.append(
                {
                    "id": track_id,
                    "title": f"{prog_name} — {mood}",
                    "mood": mood,
                    "bpm": bpm,
                    "duration": round(duration, 2),
                    "file": filename,
                    "author": "Bibliothèque AutoCut (synthèse générative FFmpeg)",
                    "source": "Générée par scripts/generate_music.py",
                    "license": "CC0 1.0 (domaine public)",
                }
            )
    (out_dir / "licenses.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return registry


if __name__ == "__main__":
    tracks = generate(force="--force" in sys.argv)
    print(f"{len(tracks)} pistes dans {settings.music_dir}")
