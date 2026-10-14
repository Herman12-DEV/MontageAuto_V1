from app.engine import subtitles

WORDS = [
    {"w": "Bonjour", "s": 0.0, "e": 0.4},
    {"w": "à", "s": 0.45, "e": 0.5},
    {"w": "tous.", "s": 0.55, "e": 0.9},
    {"w": "Voici", "s": 2.5, "e": 2.8},
    {"w": "la", "s": 2.85, "e": 2.9},
    {"w": "démo", "s": 2.95, "e": 3.3},
]


def test_at_least_five_styles_are_available():
    assert len(subtitles.STYLES) >= 5
    keys = {s["key"] for s in subtitles.public_styles()}
    assert subtitles.DEFAULT_STYLE in keys


def test_ass_highlights_one_word_per_event():
    ass = subtitles.build_ass(WORDS, "karaoke", 1080, 1920)
    events = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert len(events) == len(WORDS)
    green = "&H006EC627"
    assert all(e.count(green) == 1 for e in events)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "BONJOUR" in ass  # style en majuscules


def test_ass_lines_break_on_sentence_end_and_pause():
    lines = subtitles.display_lines(WORDS, subtitles.STYLES["karaoke"])
    assert [[w["w"] for w in line] for line in lines] == [["Bonjour", "à", "tous."], ["Voici", "la", "démo"]]


def test_watermark_is_added_for_whole_duration():
    ass = subtitles.build_ass([], "karaoke", 720, 1280, watermark="AutoCut", total_duration=12.0)
    watermark = [line for line in ass.splitlines() if ",Watermark," in line and line.startswith("Dialogue")]
    assert len(watermark) == 1
    assert watermark[0].startswith("Dialogue: 1,0:00:00.00,0:00:13.00")


def test_ass_escapes_override_characters():
    ass = subtitles.build_ass([{"w": "{\\b1}x", "s": 0, "e": 1}], "minimal", 640, 360)
    assert "{\\b1}x" not in ass
    assert "(/b1)x" in ass


def test_srt_timestamps():
    srt = subtitles.build_srt(WORDS)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,300\nBonjour à tous.\n")
    assert "2\n00:00:02,500 --> 00:00:03,700\nVoici la démo" in srt


def test_phrase_edit_keeps_timings_when_word_count_matches():
    edited = subtitles.apply_phrase_edit(WORDS[:3], "Bonsoir à tous.")
    assert [w["w"] for w in edited] == ["Bonsoir", "à", "tous."]
    assert [(w["s"], w["e"]) for w in edited] == [(w["s"], w["e"]) for w in WORDS[:3]]


def test_phrase_edit_redistributes_time_when_word_count_changes():
    edited = subtitles.apply_phrase_edit(WORDS[:3], "Salut")
    assert edited == [{"w": "Salut", "s": 0.0, "e": 0.9}]
    assert subtitles.apply_phrase_edit(WORDS[:3], "   ") == []


def test_phrases_split_on_long_pause():
    phrases = subtitles.phrases_from_words(WORDS)
    assert len(phrases) == 2
