"""Smoke tests: chart functions run on small synthetic data and write a PNG."""
import pandas as pd

from fti.charts import plot_first_sub_by_state, plot_sensitivity


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
