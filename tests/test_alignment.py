import pytest

from singlayer.alignment import calibrate


@pytest.mark.parametrize("speed,offset", [(0.8, 3), (1.25, -4), (1, 2)])
def test_slowed_sped_and_offset(speed, offset):
    points = [(p, p * speed + offset) for p in (20, 80)]
    actual_offset, actual_speed = calibrate(*points)
    assert actual_offset == pytest.approx(offset)
    assert actual_speed == pytest.approx(speed)
    # A third, unused point predicts correctly for constant speed.
    assert ((140 * speed + offset) - actual_offset) / actual_speed == pytest.approx(140)


@pytest.mark.parametrize(
    "first,second",
    [((10, 10), (12, 12)), ((10, 10), (30, 5)), ((10, 10), (30, 100)), ((float("nan"), 10), (30, 30))],
)
def test_bad_anchors_rejected(first, second):
    with pytest.raises(ValueError):
        calibrate(first, second)


def test_automatic_clock_requires_three_unique_consistent_acoustic_anchors():
    from singlayer.alignment import estimate_clock

    texts = ["first original phrase with unique words", "second distinct phrase with enough evidence",
             "third separate lyric in this original example"]
    catalog = {"lines": [{"text": text, "start": start} for text, start in zip(texts, [19, 43, 67])]}
    observed = {"lines": [{"text": text, "start": start} for text, start in zip(texts, [20, 50, 80])]}
    assert estimate_clock({"lines": observed["lines"][:2]}, catalog) is None
    assert estimate_clock(observed, catalog) == {"offset": 3, "speed": .8, "anchors": 3}
    # A cut changes the middle anchor: a constant clock must stop qualifying.
    observed["lines"][1]["start"] = 40
    assert estimate_clock(observed, catalog) is None


def test_overlapping_windows_keep_distinct_clock_anchors_and_cut_invalidates():
    from singlayer.alignment import estimate_clock

    texts = ["one unique original lyric for this sample", "another entirely separate lyrical phrase here",
             "third clear verse with sufficiently unique words"]
    catalog = {"lines": [{"text": text, "start": time} for text, time in zip(texts, [19, 43, 67])]}
    anchors = {}
    clock = None
    for text, time in zip(texts, [20, 50, 80]):
        clock = estimate_clock({"lines": [{"text": text, "start": time}]}, catalog, anchors)
    assert clock == {"offset": 3, "speed": .8, "anchors": 3}
    assert estimate_clock({"lines": [{"text": texts[1], "start": 60}]}, catalog, anchors) is None
    assert len(anchors) == 1


def test_three_independent_anchors_tolerate_one_asr_word_error_each():
    from singlayer.alignment import estimate_clock

    texts = [f"distinct{index} amber birch cedar dawn elm fern grove hazel" for index in range(3)]
    catalog = {"lines": [{"text": text, "start": time} for text, time in zip(texts, [19, 43, 67])]}
    observed = {"lines": [{"text": text.replace("amber", "ocher"), "start": time}
                          for text, time in zip(texts, [20, 50, 80])]}
    assert estimate_clock(observed, catalog) == {"offset": 3, "speed": .8, "anchors": 3}
