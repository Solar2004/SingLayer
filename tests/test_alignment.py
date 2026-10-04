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
