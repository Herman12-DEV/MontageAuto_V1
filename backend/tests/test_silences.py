from app.engine import silences

STDERR = """
[silencedetect @ 0x1] silence_start: 0
[silencedetect @ 0x1] silence_end: 1.2 | silence_duration: 1.2
[silencedetect @ 0x1] silence_start: 3.5
[silencedetect @ 0x1] silence_end: 5.0 | silence_duration: 1.5
[silencedetect @ 0x1] silence_start: 8.25
"""


def test_parse_silencedetect_handles_trailing_silence():
    assert silences.parse_silencedetect(STDERR, 10.0) == [(0.0, 1.2), (3.5, 5.0), (8.25, 10.0)]


def test_keep_segments_adds_breathing_room_and_snaps_to_frames():
    kept = silences.keep_segments([(0.0, 1.2), (3.5, 5.0), (8.25, 10.0)], 10.0, padding=0.1, fps=25)
    assert kept == [(1.08, 3.6), (4.88, 8.36)]
    frame = 1 / 25
    for start, end in kept:
        assert abs(start / frame - round(start / frame)) < 1e-6
        assert abs(end / frame - round(end / frame)) < 1e-6


def test_keep_segments_merges_when_padding_overlaps():
    kept = silences.keep_segments([(2.0, 2.15)], 4.0, padding=0.1, fps=30)
    assert kept == [(0.0, 4.0)]


def test_keep_segments_never_returns_empty_video():
    assert silences.keep_segments([(0.0, 6.0)], 6.0) == [(0.0, 6.0)]


def test_removed_count_counts_head_middle_and_tail():
    kept = [(1.0, 3.0), (4.0, 8.0)]
    assert silences.removed_count(kept, 10.0) == 3
    assert silences.removed_count([(0.0, 10.0)], 10.0) == 0


def test_video_select_expression_uses_half_frame_offset():
    expr = silences.video_select_expr([(1.0, 2.0)], 25)
    assert expr == "gte(t,0.980000)*lt(t,1.980000)"
