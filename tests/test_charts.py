"""Smoke tests: chart functions run on small synthetic data and write a PNG."""
import pandas as pd

from fti.charts import headline, plot_first_sub_by_state, plot_sensitivity, sensitivity_title


def test_plot_first_sub_by_state_writes_png(tmp_path):
    first = pd.DataFrame({
        "team": ["Arsenal", "Arsenal", "X", "Y", "Z", "X"],
        "score_state": ["winning", "losing", "winning", "drawing", "losing", "winning"],
        "clock": [72.0, 58.0, 65.0, 60.0, 55.0, 67.0],
    })
    out = tmp_path / "chart.png"
    plot_first_sub_by_state(first, out)
    assert out.exists() and out.stat().st_size > 0


def test_plot_sensitivity_writes_png(tmp_path):
    sens = pd.DataFrame({
        "variant": ["A", "B"], "score_state": ["winning", "winning"], "n_team": [18, 17],
        "diff_minutes": [5.5, 8.2], "ci95_low": [0.5, 0.2], "ci95_high": [9.5, 10.2],
    })
    out = tmp_path / "forest.png"
    plot_sensitivity(sens, out)
    assert out.exists() and out.stat().st_size > 0


def _comparison(diffs, excludes):
    return pd.DataFrame({"score_state": ["winning", "drawing", "losing"],
                         "diff_minutes": diffs, "ci_excludes_zero": excludes})


def _perms(ps):
    return pd.DataFrame({"score_state": ["winning", "drawing", "losing"], "permutation_p": ps})


def test_headline_claims_direction_only_with_both_ci_and_permutation_evidence():
    title, state = headline("Arsenal", _comparison([8.0, 6.5, 1.3], [True, True, False]),
                            _perms([0.010, 0.22, 0.83]))
    assert title == "When winning, Arsenal's first tactical change came later than the league's"
    assert state == "winning"  # drawing excluded: its p-value fails the Bonferroni threshold


def test_headline_says_no_clear_difference_when_evidence_is_weak():
    title, state = headline("Leicester City", _comparison([-4.0, 2.0, 1.0], [True, False, False]),
                            _perms([0.04, 0.5, 0.7]))  # 0.04 > 0.05/3
    assert title.startswith("No clear difference") and state is None


def test_headline_reports_earlier_for_negative_gap():
    title, _ = headline("X", _comparison([-7.0, 0.5, 1.0], [True, False, False]), _perms([0.005, 0.6, 0.7]))
    assert "came earlier" in title


def test_sensitivity_title_only_claims_robustness_when_all_variants_agree():
    rows = pd.DataFrame({"ci95_low": [0.5, 0.2], "ci95_high": [9.5, 10.2]})
    assert "stays above zero" in sensitivity_title(rows, "winning", "Arsenal")
    mixed = pd.DataFrame({"ci95_low": [0.5, -1.0], "ci95_high": [9.5, 10.2]})
    assert "stays" not in sensitivity_title(mixed, "winning", "Arsenal")
