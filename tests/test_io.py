import pandas as pd
import pytest

from sktime_cli._errors import CliError
from sktime_cli._io import parse_fh, parse_size, read_any, write_any


def test_csv_roundtrip_period_index(airline_csv):
    data = read_any(airline_csv)
    assert data.kind == "series"
    assert isinstance(data.obj, pd.Series)
    assert isinstance(data.obj.index, pd.PeriodIndex)
    assert len(data.obj) == 144


def test_json_roundtrip(tmp_path, airline_csv):
    original = read_any(airline_csv).obj
    path = tmp_path / "airline.json"
    write_any(original, path)
    back = read_any(path)
    assert len(back.obj) == 144
    assert back.obj.iloc[0] == original.iloc[0]


def test_ts_roundtrip(unit_test_ts):
    data = read_any(unit_test_ts)
    assert data.kind == "panel"
    assert data.y is not None
    assert len(data.obj) == len(data.y) == 42


def test_read_missing_file():
    with pytest.raises(CliError) as excinfo:
        read_any("does-not-exist.csv")
    assert excinfo.value.code == "not_found"


def test_parse_fh_range():
    fh = parse_fh("1:12")
    assert list(fh.to_pandas()) == list(range(1, 13))


def test_parse_fh_list():
    assert list(parse_fh("1,2,12").to_pandas()) == [1, 2, 12]


def test_parse_fh_single():
    assert list(parse_fh("6").to_pandas()) == [6]


def test_parse_fh_invalid():
    with pytest.raises(CliError) as excinfo:
        parse_fh("abc")
    assert excinfo.value.code == "usage"


@pytest.mark.parametrize(("text", "expected"), [("12", 12), ("0.2", 0.2), (None, None)])
def test_parse_size(text, expected):
    assert parse_size(text) == expected


def test_parse_size_invalid():
    with pytest.raises(CliError):
        parse_size("abc")
