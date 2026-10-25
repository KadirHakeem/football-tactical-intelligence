"""Tests for deciding whether the substitutions table needs rebuilding."""
import os

from fti.substitutions import COLUMNS, table_is_current


def _write_table(path):
    path.write_text(",".join(COLUMNS + ["match_date", "sub_number"]) + "\n", encoding="utf-8")


def test_missing_table_is_not_current(tmp_path):
    assert table_is_current(tmp_path / "substitutions.csv", sources=[]) is False


def test_table_newer_than_inputs_is_current(tmp_path):
    source, out = tmp_path / "events.pkl", tmp_path / "substitutions.csv"
    source.write_text("x")
    _write_table(out)
    os.utime(source, (1_000, 1_000))
    os.utime(out, (2_000, 2_000))
    assert table_is_current(out, sources=[source]) is True


def test_table_older_than_an_input_is_stale(tmp_path):
    source, out = tmp_path / "events.pkl", tmp_path / "substitutions.csv"
    source.write_text("x")
    _write_table(out)
    os.utime(out, (1_000, 1_000))
    os.utime(source, (2_000, 2_000))   # input changed after the table was built
    assert table_is_current(out, sources=[source]) is False


def test_table_missing_new_columns_is_stale(tmp_path):
    out = tmp_path / "substitutions.csv"
    out.write_text("match_id,team,minute\n", encoding="utf-8")
    assert table_is_current(out, sources=[]) is False
