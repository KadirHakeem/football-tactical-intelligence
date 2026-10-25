"""Tests for the permutation test."""
from fti.robustness import permutation_test_median_diff


def test_permutation_p_is_small_for_a_clear_gap():
    later = [70, 71, 72, 73, 74, 75, 76, 77, 78, 79]
    earlier = [55, 56, 57, 58, 59, 60, 61, 62, 63, 64]
    assert permutation_test_median_diff(later, earlier) < 0.01


def test_permutation_p_is_large_for_identical_groups():
    values = [50, 55, 60, 65, 70, 75, 80]
    assert permutation_test_median_diff(values, values) > 0.5


def test_permutation_p_is_reproducible():
    a, b = [60, 65, 70, 72], [55, 58, 61, 66, 69]
    assert permutation_test_median_diff(a, b) == permutation_test_median_diff(a, b)
