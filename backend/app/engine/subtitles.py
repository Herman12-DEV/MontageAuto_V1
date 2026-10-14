"""Sous-titres : styles (F-ST-04), karaoké mot à mot (F-ST-03), export .ass/.srt (F-ST-05)
et application des corrections de l'éditeur (F-ST-06)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

Word = dict  # {"w": str, "s": float, "e": float}


@dataclass(frozen=True)
class SubtitleStyle:
    key: str
    label: str
    description: str
    font: str
    bold: bool
    uppercase: bool
    text_color: str  # #RRGGBB
    active_color: str
    outline_color: str
    box: bool  # texte sur fond (BorderStyle 3)
    size: float  # proportion du petit côté de l'image
    outline: float
    shadow: float
    align: int  # pavé numérique ASS : 2 = bas centre, 5 = centre, 8 = haut centre
    margin_v: float  # proportion de la hauteur
    max_words: int
    max_chars: int
    pop: bool  # mot actif légèrement agrandi


STYLES: dict[str, SubtitleStyle] = {
    s.key: s
    for s in (
        SubtitleStyle(
            "karaoke", "Karaoké vert", "Gros texte blanc, mot actif en vert.",
            "Arial Black", True, True, "#FFFFFF", "#27C66E", "#000000", False,
            0.074, 0.0055, 0.002, 2, 0.24, 3, 18, True,
        ),
        SubtitleStyle(
            "jaune", "Impact jaune", "Police Impact, mot actif jaune, contour épais.",
            "Impact", False, True, "#FFFFFF", "#F2B812", "#000000", False,
            0.085, 0.007, 0.0, 2, 0.24, 3, 16, True,
        ),
        SubtitleStyle(
            "boite", "Boîte noire", "Texte sur bandeau sombre, mot actif vert.",
            "Arial", True, False, "#FFFFFF", "#27C66E", "#0B0C0B", True,
            0.058, 0.012, 0.0, 2, 0.2, 4, 26, False,
        ),
        SubtitleStyle(
            "minimal", "Minimal", "Discret, en bas de l’image, casse normale.",
            "Arial", False, False, "#FFFFFF", "#9AEFB8", "#000000", False,
            0.05, 0.003, 0.0015, 2, 0.08, 6, 34, False,
        ),
        SubtitleStyle(
            "neon", "Néon", "Mot actif cyan lumineux, ombre portée.",
            "Verdana", True, True, "#FFFFFF", "#3FE0FF", "#1A0638", False,
            0.068, 0.005, 0.006, 2, 0.24, 3, 18, True,
        ),
        SubtitleStyle(
            "centre", "Plein centre", "Très gros texte au centre de l’image.",
            "Arial Black", True, True, "#FFFFFF", "#27C66E", "#000000", False,
            0.095, 0.0065, 0.002, 5, 0.0, 2, 14, True,
        ),
    )
}

DEFAULT_STYLE = "karaoke"


def public_styles() -> list[dict]:
    return [asdict(s) for s in STYLES.values()]


# --- Regroupement ----------------------------------------------------------

_SENTENCE_END = re.compile(r"[.!?…]$")


def phrases_from_words(words: list[Word]) -> list[dict]:
    """Découpe en phrases éditables (pauses, ponctuation, 14 mots max)."""
    phrases: list[dict] = []
    current: list[Word] = []
    for word in words:
        if current and (
            word["s"] - current[-1]["e"] > 1.0
            or _SENTENCE_END.search(current[-1]["w"])
            or len(current) >= 14
        ):
            phrases.append({"words": current})
            current = []
        current.append(word)
    if current:
        phrases.append({"words": current})
    return phrases


def display_lines(words: list[Word], style: SubtitleStyle) -> list[list[Word]]:
    lines: list[list[Word]] = []
    current: list[Word] = []
    chars = 0
    for word in words:
        too_long = chars + len(word["w"]) + (1 if current else 0) > style.max_chars
        if current and (
            len(current) >= style.max_words
            or too_long
            or word["s"] - current[-1]["e"] > 0.7
            or _SENTENCE_END.search(current[-1]["w"])
            or word["e"] - current[0]["s"] > 3.5
        ):
            lines.append(current)
            current, chars = [], 0
        current.append(word)
        chars += len(word["w"]) + (1 if len(current) > 1 else 0)
    if current:
        lines.append(current)
    return lines


# --- Corrections manuelles ------------------------------------------------


def apply_phrase_edit(words: list[Word], new_text: str) -> list[Word]:
    """Remplace le texte d'une phrase en conservant au mieux le minutage des mots."""
    tokens = new_text.split()
    if not tokens or not words:
        return []
    if len(tokens) == len(words):
        return [{**w, "w": t} for w, t in zip(words, tokens, strict=True)]
    start, end = words[0]["s"], words[-1]["e"]
    weights = [len(t) + 1 for t in tokens]
    total = sum(weights)
    out: list[Word] = []
    cursor = start
    for token, weight in zip(tokens, weights, strict=True):
        span = (end - start) * weight / total
        out.append({"w": token, "s": round(cursor, 3), "e": round(cursor + span, 3)})
        cursor += span
    return out


# --- Rendu ASS / SRT ------------------------------------------------------


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    value = hex_color.lstrip("#")
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(seconds: float) -> str:
    ms = round(max(0.0, seconds) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _clean(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _line_windows(lines: list[list[Word]], total: float | None) -> list[tuple[float, float]]:
    """Fenêtre d'affichage de chaque ligne : prolongée jusqu'à 0,4 s sans chevaucher la suivante."""
    windows = []
    for i, line in enumerate(lines):
        start = line[0]["s"]
        end = line[-1]["e"] + 0.4
        if i + 1 < len(lines):
            end = min(end, lines[i + 1][0]["s"])
        if total is not None:
            end = min(end, total)
        windows.append((start, max(end, line[-1]["e"])))
    return windows


def build_ass(
    words: list[Word],
    style_key: str,
    width: int,
    height: int,
    *,
    watermark: str | None = None,
    total_duration: float | None = None,
) -> str:
    style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
    short = min(width, height)
    size = max(18, round(short * style.size))
    outline = max(1, round(short * style.outline, 1))
    shadow = round(short * style.shadow, 1)
    margin_v = round(height * style.margin_v)
    margin_h = round(width * 0.07)
    back = _ass_color(style.outline_color, 0x30 if style.box else 0x80)
    border_style = 3 if style.box else 1
    wm_size = max(14, round(short * 0.032))

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Main,{style.font},{size},{_ass_color(style.text_color)},"
        f"{_ass_color(style.active_color)},{_ass_color(style.outline_color)},{back},"
        f"{-1 if style.bold else 0},0,0,0,100,100,0,0,{border_style},{outline},{shadow},"
        f"{style.align},{margin_h},{margin_h},{margin_v},1",
        f"Style: Watermark,Arial,{wm_size},{_ass_color('#FFFFFF', 0x60)},"
        f"{_ass_color('#FFFFFF', 0x60)},{_ass_color('#000000', 0x90)},{_ass_color('#000000', 0xFF)},"
        f"-1,0,0,0,100,100,1,0,1,1,0,9,{round(width * 0.04)},{round(width * 0.04)},"
        f"{round(height * 0.03)},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events: list[str] = []
    active = _ass_color(style.active_color)
    pop = r"\fscx112\fscy112" if style.pop else ""
    lines = display_lines(words, style)
    for line, (line_start, line_end) in zip(lines, _line_windows(lines, total_duration), strict=True):
        texts = [_clean(w["w"].upper() if style.uppercase else w["w"]) for w in line]
        for i, word in enumerate(line):
            start = line_start if i == 0 else word["s"]
            end = line[i + 1]["s"] if i + 1 < len(line) else line_end
            if end <= start:
                continue
            parts = [
                f"{{\\c{active}{pop}}}{t}{{\\r}}" if j == i else t for j, t in enumerate(texts)
            ]
            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Main,,0,0,0,,{' '.join(parts)}"
            )
    if watermark:
        end = total_duration if total_duration else (words[-1]["e"] + 1 if words else 3600)
        events.append(
            f"Dialogue: 1,{_ass_time(0)},{_ass_time(end + 1)},Watermark,,0,0,0,,{_clean(watermark)}"
        )
    return "\n".join(header + events) + "\n"


def build_srt(words: list[Word], style_key: str = DEFAULT_STYLE) -> str:
    style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
    # Lignes un peu plus longues que l'incrustation : plus confortable dans un lecteur.
    relaxed = SubtitleStyle(**{**asdict(style), "max_words": 8, "max_chars": 42})
    lines = display_lines(words, relaxed)
    blocks = []
    for index, (line, (start, end)) in enumerate(
        zip(lines, _line_windows(lines, None), strict=True), start=1
    ):
        text = " ".join(w["w"] for w in line)
        blocks.append(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    return "\n".join(blocks)


def plain_text(words: list[Word]) -> str:
    return "\n".join(" ".join(w["w"] for w in p["words"]) for p in phrases_from_words(words))
