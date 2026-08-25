"""The long-form flattening schema for probabilistic and detection results."""

import pandas as pd
import pytest

from sktime_cli import _frames


@pytest.fixture
def interval_frame():
    columns = pd.MultiIndex.from_tuples(
        [
            ("y", 0.8, "lower"),
            ("y", 0.8, "upper"),
            ("y", 0.95, "lower"),
            ("y", 0.95, "upper"),
        ]
    )
    return pd.DataFrame(
        [[1.0, 2.0, 0.5, 2.5], [3.0, 4.0, 2.5, 4.5]],
        index=pd.period_range("2020-01", periods=2, freq="M"),
        columns=columns,
    )


def test_melt_produces_the_documented_columns(interval_frame):
    long = _frames.melt(interval_frame, _frames.INTERVAL_LEVELS)
    assert list(long.columns) == ["variable", "coverage", "bound", "value"]
    assert len(long) == 8  # 2 timepoints x 2 coverages x 2 bounds
    assert long.index.name == "time"


def test_melt_column_count_is_stable_across_coverages(interval_frame):
    """The point of long form: more coverages add rows, never columns."""
    one = _frames.melt(
        interval_frame[[("y", 0.8, "lower"), ("y", 0.8, "upper")]],
        _frames.INTERVAL_LEVELS,
    )
    many = _frames.melt(interval_frame, _frames.INTERVAL_LEVELS)
    assert list(one.columns) == list(many.columns)
    assert len(many) > len(one)


def test_melt_preserves_a_multiindex_row_index():
    columns = pd.MultiIndex.from_tuples([("y", 0.9, "lower"), ("y", 0.9, "upper")])
    index = pd.MultiIndex.from_tuples([("a", 1), ("a", 2)], names=["inst", "time"])
    frame = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=index, columns=columns)
    long = _frames.melt(frame, _frames.INTERVAL_LEVELS)
    assert long.index.names == ["inst", "time"]
    assert len(long) == 4


def test_widen_joins_levels_with_a_separator(interval_frame):
    wide = _frames.widen(interval_frame)
    assert "y__0.8__lower" in wide.columns
    assert not isinstance(wide.columns, pd.MultiIndex)


def test_widen_leaves_flat_columns_alone():
    frame = pd.DataFrame({"a": [1], "b": [2]})
    assert list(_frames.widen(frame).columns) == ["a", "b"]


def test_segments_to_frame_flattens_intervals():
    segments = pd.DataFrame(
        {"ilocs": [pd.Interval(0, 2), pd.Interval(2, 5)], "label": [1, 2]}
    )
    out = _frames.segments_to_frame(segments)
    assert list(out.columns) == ["start", "end", "label"]
    assert out["start"].tolist() == [0, 2]
    assert out["end"].tolist() == [2, 5]


def test_segments_to_frame_passes_dense_labels_through():
    """Detectors that return a label per timepoint need no flattening."""
    dense = pd.DataFrame({"ilocs": [0, 0, 1, 1]})
    out = _frames.segments_to_frame(dense)
    assert out["ilocs"].tolist() == [0, 0, 1, 1]


def test_to_frame_normalises_every_result_type():
    import numpy as np

    assert list(_frames.to_frame(pd.Series([1, 2])).columns) == ["value"]
    assert _frames.to_frame(np.array([[1, 2], [3, 4]])).shape == (2, 2)
    assert list(_frames.to_frame(pd.DataFrame({"a": [1]})).columns) == ["a"]
