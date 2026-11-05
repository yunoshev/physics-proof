# generated from brief/11 · part 11 owns this file
"""A range distance counts from the measured value (brief §40).

``delta_sigma`` is the distance of the measured value from the
nearer bound, in σ — ``(value - max) / σ`` above the range,
``(min - value) / σ`` below it, and 0 inside — like the world
chips. The outcome rule is unchanged: outside (or below) exactly
when that distance exceeds 2.
"""

from src.validate.ranges import score_range


def _check(value, sigma, low, high):
    return {"value": value, "sigma": sigma,
            "range": {"min": low, "max": high}}


def test_wall_run_18_distance_from_value():
    # Wall run 18: 14.066 ± 2.504 m against a maximum of 5.5 m.
    # The old wording counted the 2σ interval's edge (1.4σ); the
    # value stands 3.42σ above the range.
    scored = score_range(_check(14.066, 2.504, 0.0, 5.5))
    assert scored["outcome"] == "outside", scored
    assert scored["side"] == "above", scored
    assert abs(scored["delta_sigma"] - 3.42) < 0.01, scored


def test_wall_run_15_distance_from_value():
    # Wall run 15: 10.145 ± 0.531 m against a maximum of 4.0 m.
    scored = score_range(_check(10.145, 0.531, 0.0, 4.0))
    assert scored["outcome"] == "outside", scored
    assert scored["side"] == "above", scored
    assert abs(scored["delta_sigma"] - 11.57) < 0.01, scored


def test_moon_run_23_distance_from_value():
    # Moon run 23: 0.288 ± 0.021 m against a minimum of 0.41 m.
    scored = score_range(_check(0.288, 0.021, 0.41, 0.60))
    assert scored["outcome"] == "below", scored
    assert scored["side"] == "below", scored
    assert abs(scored["delta_sigma"] - 5.8) < 0.1, scored


def test_value_near_maximum_is_inside_with_zero_delta():
    # A value 1.9σ above the maximum is inside, with delta_sigma 0.
    scored = score_range(_check(5.5 + 1.9 * 2.504, 2.504, 0.0, 5.5))
    assert scored["outcome"] == "inside", scored
    assert scored["delta_sigma"] == 0.0, scored
